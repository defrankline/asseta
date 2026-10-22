"""Training orchestration: snapshots -> readiness -> split -> baseline + candidate -> evaluation -> tracked run.

This is the only place the pieces are wired together, and it is deliberately free of I/O other than the tracker:
the intelligence module loads snapshots, calls `train_and_evaluate`, and writes `model_version` /
`model_evaluation` rows from the returned `TrainingOutcome`. A tenant without enough history gets an
`INSUFFICIENT_DATA` outcome with reasons and no model — the documented "startup with no history" behaviour.
"""

from __future__ import annotations

import hashlib
import pickle
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from asseta.ml.baseline import RobustZScoreBaseline
from asseta.ml.datasets import (
    DatasetManifest,
    FeatureMatrix,
    Readiness,
    ReadinessStatus,
    SplitConfig,
    SufficiencyCriteria,
    assess_readiness,
    build_manifest,
    build_matrix,
    default_split_config,
    temporal_split,
)
from asseta.ml.evaluation import EvaluationResult, PromotionCriteria, ScorerMetrics, evaluate_promotion, evaluate_scorer
from asseta.ml.features import R1_FEATURES, FeatureRegistry, FeatureSnapshot
from asseta.ml.models import IsolationForestModel, ScoredRow
from asseta.ml.tracking import DEFAULT_EXPERIMENT, ExperimentTracker, NullTracker, TrackingError

ALGORITHM = "isolation_forest"
BASELINE_ALGORITHM = "robust_zscore"


class TrainingStatus(StrEnum):
    TRAINED = "TRAINED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, eq=False)
class ModelBundle:
    """Everything inference needs, pickled as the model artifact (baseline travels with the candidate)."""

    tenant_id: str
    feature_set_hash: str
    feature_codes: tuple[str, ...]
    baseline: RobustZScoreBaseline
    candidate: IsolationForestModel
    seed: int

    def score(self, matrix: FeatureMatrix) -> tuple[list[ScoredRow], list[ScoredRow]]:
        """(baseline rows, candidate rows) for a matrix built with the same feature set."""
        if matrix.feature_codes != self.feature_codes or matrix.tenant_id != self.tenant_id:
            raise ValueError("matrix does not match the bundle's tenant or feature set")
        return self.baseline.score(matrix), self.candidate.score(matrix)


@dataclass(frozen=True, eq=False)
class TrainingOutcome:
    status: TrainingStatus
    readiness: Readiness
    feature_set_hash: str
    algorithm: str
    manifest: DatasetManifest | None = None
    baseline_metrics: ScorerMetrics | None = None
    model_metrics: ScorerMetrics | None = None
    evaluation: EvaluationResult | None = None
    run_id: str | None = None
    tracking_error: str | None = None
    model_bytes: bytes | None = None
    model_sha256: str | None = None

    @property
    def has_model(self) -> bool:
        return self.model_bytes is not None


def load_model_bundle(data: bytes, expected_sha256: str) -> ModelBundle:
    """Unpickle a bundle only after its digest matches the one recorded at training time.

    Bundles are produced by `train_and_evaluate` and stored in our own MLflow/MinIO; the digest check (kept in the
    governance tables) stops a swapped artifact from being loaded.
    """
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("model artifact digest mismatch")
    bundle = pickle.loads(data)  # noqa: S301 - trusted artifact, integrity verified above
    if not isinstance(bundle, ModelBundle):
        raise TypeError("artifact is not a ModelBundle")
    return bundle


def train_and_evaluate(
    snapshots: Iterable[FeatureSnapshot],
    criteria: SufficiencyCriteria | None = None,
    tracker: ExperimentTracker | None = None,
    seed: int = 0,
    *,
    promotion: PromotionCriteria | None = None,
    registry: FeatureRegistry = R1_FEATURES,
    split_config: SplitConfig | None = None,
    contamination: float | str = "auto",
    experiment: str = DEFAULT_EXPERIMENT,
) -> TrainingOutcome:
    criteria = criteria or SufficiencyCriteria()
    promotion = promotion or PromotionCriteria()
    tracker = tracker or NullTracker()
    fs_hash = registry.feature_set_hash()
    snaps = list(snapshots)
    if not snaps:
        return TrainingOutcome(TrainingStatus.INSUFFICIENT_DATA, assess_readiness(None, criteria), fs_hash, ALGORITHM)
    matrix = build_matrix(snaps, registry)  # raises TenantMixingError: a caller bug, never silently pooled
    readiness = assess_readiness(matrix, criteria)
    if not readiness.ready:
        return TrainingOutcome(TrainingStatus.INSUFFICIENT_DATA, readiness, fs_hash, ALGORITHM)
    try:
        config = split_config or default_split_config(matrix, purge=registry.max_window)
    except ValueError as exc:
        reasons = (*readiness.reasons, str(exc))
        insufficient = Readiness(ReadinessStatus.INSUFFICIENT_DATA, reasons, readiness.observed, criteria)
        return TrainingOutcome(TrainingStatus.INSUFFICIENT_DATA, insufficient, fs_hash, ALGORITHM)
    split = temporal_split(matrix, config)
    readiness = assess_readiness(matrix, criteria, split)
    manifest = build_manifest(matrix, split, fs_hash)
    if not readiness.ready:
        return TrainingOutcome(TrainingStatus.INSUFFICIENT_DATA, readiness, fs_hash, ALGORITHM, manifest=manifest)

    threshold = promotion.alert_threshold
    baseline, baseline_metrics = evaluate_scorer(RobustZScoreBaseline, split, seed=seed, alert_threshold=threshold)
    candidate, model_metrics = evaluate_scorer(
        lambda: IsolationForestModel(random_state=seed, contamination=contamination),
        split,
        seed=seed,
        alert_threshold=threshold,
    )
    evaluation = evaluate_promotion(baseline_metrics, model_metrics, readiness, promotion)
    assert isinstance(baseline, RobustZScoreBaseline) and isinstance(candidate, IsolationForestModel)
    bundle = ModelBundle(matrix.tenant_id, fs_hash, matrix.feature_codes, baseline, candidate, seed)
    model_bytes = pickle.dumps(bundle, protocol=pickle.HIGHEST_PROTOCOL)
    model_sha = hashlib.sha256(model_bytes).hexdigest()

    run_id: str | None = None
    tracking_error: str | None = None
    try:
        run_id = tracker.log_run(
            experiment=experiment,
            run_name=f"{ALGORITHM}-{matrix.tenant_id}",
            params={
                "algorithm": ALGORITHM,
                "baseline_algorithm": BASELINE_ALGORITHM,
                "seed": seed,
                "contamination": str(contamination),
                "feature_set_hash": fs_hash,
                "train_end": manifest.train_end,
                "validation_end": manifest.validation_end,
            },
            metrics={k: float(v) for k, v in evaluation.metrics.items()} | {"passed": float(evaluation.passed)},
            artifacts={"manifest.json": manifest.to_json().encode(), "model.pkl": model_bytes},
            tags={"asseta.tenant_id": matrix.tenant_id, "asseta.model_sha256": model_sha},
        )
    except TrackingError as exc:
        tracking_error = str(exc)
    return TrainingOutcome(
        status=TrainingStatus.TRAINED,
        readiness=readiness,
        feature_set_hash=fs_hash,
        algorithm=ALGORITHM,
        manifest=manifest,
        baseline_metrics=baseline_metrics,
        model_metrics=model_metrics,
        evaluation=evaluation,
        run_id=run_id,
        tracking_error=tracking_error,
        model_bytes=model_bytes,
        model_sha256=model_sha,
    )
