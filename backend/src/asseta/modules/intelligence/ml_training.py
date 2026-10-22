"""Training job: one tenant's snapshots -> `train_and_evaluate` -> governance rows (ADR-007 "Model lifecycle").

* Snapshots are read in the tenant's own RLS scope and the dataset refuses any foreign row (pooled training is OFF).
* Every attempt records a `model_readiness` row. `INSUFFICIENT_DATA` creates **no** model version.
* A trained model is stored as an immutable, content-addressed object under the platform-private prefix
  `platform/ml-models/<tenant>/<name>/<sha256>.pkl` (never in Postgres) and recorded as `model_version` (EVALUATED)
  with an immutable `model_evaluation` (candidate vs the robust-z baseline) and a TRAIN lifecycle entry.
* MLflow is optional and never blocks: when it is not configured or unreachable the version is still persisted with
  `mlflow_run_id = NULL` and the reason in `tracking_note`. MLflow HTTP retries are capped so a dead server costs at
  most one request timeout (`MLFLOW_HTTP_REQUEST_MAX_RETRIES=0`, `MLFLOW_HTTP_REQUEST_TIMEOUT=10` unless set).
* Bounded runtime: at most `TRAINING_LOOKBACK_WEEKS` of snapshots; the synthetic 12x16 fleet trains in < 1 s.
"""

import math
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.config import Settings
from asseta.core.storage import ObjectStore
from asseta.ml.datasets import SufficiencyCriteria, TenantMixingError
from asseta.ml.evaluation import PromotionCriteria
from asseta.ml.features import R1_FEATURES, FeatureRegistry
from asseta.ml.tracking import TRACKING_URI_ENV, ExperimentTracker, tracker_from_env
from asseta.ml.training import TrainingOutcome, train_and_evaluate
from asseta.modules.intelligence.feature_store import load_snapshots
from asseta.modules.intelligence.ml_models import (
    ANOMALY_MODEL_NAME,
    SOURCE_OBSERVED,
    ModelAction,
    ModelAlgorithm,
    ModelApproval,
    ModelEvaluation,
    ModelReadiness,
    ModelStatus,
    ModelVersion,
    ReadinessState,
)

NOT_CONFIGURED = "MLflow tracking is not configured (ASSETA_MLFLOW_TRACKING_URI unset); run recorded only in Asseta."
ARTIFACT_PREFIX = "platform/ml-models"


def tracker_from_settings(settings: Settings) -> ExperimentTracker:
    """`Settings.mlflow_tracking_uri` (env `ASSETA_MLFLOW_TRACKING_URI`, also read from `.env`) -> tracker."""
    uri = (settings.mlflow_tracking_uri or "").strip()
    if uri:
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "0")
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "10")
    return tracker_from_env({TRACKING_URI_ENV: uri})


def clean_json(value: Any) -> Any:
    """JSONB-safe copy: NaN/inf become null (Postgres JSON has no NaN)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [clean_json(v) for v in value]
    return value


@dataclass(frozen=True)
class TrainingRunResult:
    readiness: ModelReadiness
    model: ModelVersion | None
    evaluation: ModelEvaluation | None


def _iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _record_model(
    session: Session,
    tenant_id: uuid.UUID,
    outcome: TrainingOutcome,
    now: datetime,
    store: ObjectStore,
    actor: AuditActor,
    seed: int,
    name: str,
    criteria: SufficiencyCriteria,
    promotion: PromotionCriteria,
    source: str,
) -> tuple[ModelVersion, ModelEvaluation]:
    assert outcome.model_bytes is not None and outcome.model_sha256 is not None
    assert outcome.manifest is not None and outcome.evaluation is not None
    assert outcome.baseline_metrics is not None and outcome.model_metrics is not None
    number = int(
        session.execute(
            select(func.coalesce(func.max(ModelVersion.version), 0)).where(
                ModelVersion.tenant_id == tenant_id, ModelVersion.name == name
            )
        ).scalar_one()
    )
    key = f"{ARTIFACT_PREFIX}/{tenant_id}/{name}/{outcome.model_sha256}.pkl"
    store.put_immutable(key, outcome.model_bytes, "application/octet-stream", outcome.model_sha256)
    splits = outcome.manifest.splits
    model = ModelVersion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        version=number + 1,
        algorithm=ModelAlgorithm.ISOLATION_FOREST,
        baseline_algorithm=ModelAlgorithm.ROBUST_Z_BASELINE,
        feature_set_hash=outcome.feature_set_hash,
        training_window_start=_iso(splits["train"].start),
        training_window_end=_iso(splits["test"].end) or _iso(splits["train"].end),
        manifest=clean_json(outcome.manifest.to_dict() | {"snapshot_source": source}),
        mlflow_run_id=outcome.run_id,
        tracking_note=None if outcome.run_id else (outcome.tracking_error or NOT_CONFIGURED),
        artifact_sha256=outcome.model_sha256,
        artifact_key=key,
        artifact_size_bytes=len(outcome.model_bytes),
        seed=seed,
        status=ModelStatus.TRAINED,
        status_changed_at=now,
        created_by=actor.user_id,
        created_at=now,
    )
    session.add(model)
    session.flush()
    ev = outcome.evaluation
    evaluation = ModelEvaluation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        model_version_id=model.id,
        metrics=clean_json(
            {
                "baseline": outcome.baseline_metrics.as_dict(),
                "candidate": outcome.model_metrics.as_dict(),
                "recall_lift": ev.metrics.get("recall_lift"),
            }
        ),
        readiness=clean_json(
            {
                "status": outcome.readiness.status.value,
                "reasons": list(outcome.readiness.reasons),
                "observed": dict(outcome.readiness.observed),
            }
        ),
        criteria=clean_json({"promotion": asdict(promotion), "sufficiency": asdict(criteria)}),
        passed=ev.passed,
        reasons=list(ev.reasons),
        evaluated_at=now,
    )
    session.add(evaluation)
    session.flush()
    model.status, model.status_changed_at = ModelStatus.EVALUATED, now
    session.add(
        ModelApproval(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            model_version_id=model.id,
            model_name=name,
            action=ModelAction.TRAIN,
            from_status=None,
            to_status=ModelStatus.EVALUATED,
            reason=f"Trained on {splits['train'].rows} rows; evaluation {'passed' if ev.passed else 'did not pass'}.",
            decided_by=actor.user_id,
            decided_at=now,
        )
    )
    session.flush()
    return model, evaluation


def train_tenant(
    session: Session,
    tenant_id: uuid.UUID,
    now: datetime,
    store: ObjectStore,
    tracker: ExperimentTracker,
    actor: AuditActor,
    *,
    seed: int = 0,
    name: str = ANOMALY_MODEL_NAME,
    criteria: SufficiencyCriteria | None = None,
    promotion: PromotionCriteria | None = None,
    registry: FeatureRegistry = R1_FEATURES,
    source: str = SOURCE_OBSERVED,
) -> TrainingRunResult:
    """Train one tenant's model. Governance rows are written in the caller's (platform/system) scope.

    `source` is `observed` for every real run; only the development demo trains on `synthetic` snapshots (recorded
    in the manifest as `snapshot_source`, and such a model can never be approved or activated)."""
    criteria, promotion = criteria or SufficiencyCriteria(), promotion or PromotionCriteria()
    snaps = load_snapshots(session, tenant_id, now, registry, source=source)
    if any(s.tenant_id != str(tenant_id) for s in snaps):
        raise TenantMixingError("snapshots of another tenant reached this training run")
    outcome = train_and_evaluate(snaps, criteria, tracker, seed, promotion=promotion, registry=registry)
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"ml:{tenant_id}:{name}"})
    model, evaluation = None, None
    if outcome.has_model:
        model, evaluation = _record_model(
            session, tenant_id, outcome, now, store, actor, seed, name, criteria, promotion, source
        )
    readiness = ModelReadiness(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        model_name=name,
        status=ReadinessState(outcome.readiness.status.value),
        reasons=list(outcome.readiness.reasons),
        observed=clean_json(dict(outcome.readiness.observed)),
        minimums=clean_json(asdict(criteria)),
        feature_set_hash=outcome.feature_set_hash,
        snapshot_rows=len(snaps),
        model_version_id=model.id if model else None,
        computed_at=now,
    )
    session.add(readiness)
    AuditService(session).record(
        actor=actor,
        action="platform.ml.training.completed",
        entity_type="model_version" if model else "model_readiness",
        entity_id=model.id if model else readiness.id,
        tenant_id=tenant_id,
        after=clean_json(
            {
                "readiness": readiness.status.value,
                "model_version": model.version if model else None,
                "passed": evaluation.passed if evaluation else None,
                "mlflow_run_id": outcome.run_id,
                "tracking_note": model.tracking_note if model else None,
            }
        ),
    )
    session.flush()
    return TrainingRunResult(readiness, model, evaluation)
