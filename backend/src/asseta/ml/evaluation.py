"""Label-free evaluation and promotion criteria (ADR-007 "Model lifecycle").

R1 has no confirmed-incident labels, so a model is judged on three proxies, all deterministic given a seed:

1. **Injected anomalies** — held-out *test* rows are copied and perturbed in documented, physically plausible ways
   (see `Perturbation`); recall@k / precision@k measure how many land at the top of the ranking, for the baseline
   and the candidate alike, with k = number of injected rows.
2. **Alert rate** — fraction of *clean* test rows whose calibrated score crosses the alert threshold. Calibration is
   fitted on the validation split, so measuring on test (not validation) keeps this an honest false-positive proxy.
3. **Stability** — recall@k across expanding time folds inside train+validation; a model whose recall swings wildly
   from period to period is not ready to be trusted.

A candidate is promotable only if it beats the baseline by a stated margin, stays under the alert-rate ceiling, is
stable, is calibrated and the tenant's data is READY. Promotion still requires explicit human approval elsewhere.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import timedelta
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from asseta.ml.datasets import DatasetSplit, FeatureMatrix, FloatArray, Readiness
from asseta.ml.models import AnomalyScorer

BoolArray = npt.NDArray[np.bool_]


class Perturbation(StrEnum):
    FUEL_DOUBLED = "FUEL_DOUBLED"  # fuel_litres and litres_per_meter_hour x2 (fuel logged but not burned on the job)
    ENGINE_WITHOUT_METER = "ENGINE_WITHOUT_METER"  # engine ran, meter hours not captured (gap = engine hours)
    EXPENSE_SPIKE = "EXPENSE_SPIKE"  # expense_total x3 plus three fleet medians
    OFF_SITE_ACTIVITY = "OFF_SITE_ACTIVITY"  # +10h outside geofence, x3 distance, +2 sites
    CASH_HELD = "CASH_HELD"  # cash_outstanding raised by three fleet spreads


Row = FloatArray
_Apply = Callable[[Row, Mapping[str, int], FloatArray, FloatArray], bool]


def _has(row: Row, col: Mapping[str, int], *codes: str) -> bool:
    return all(c in col and math.isfinite(row[col[c]]) for c in codes)


def _fuel_doubled(row: Row, col: Mapping[str, int], _med: FloatArray, _sd: FloatArray) -> bool:
    if not _has(row, col, "fuel_litres", "litres_per_meter_hour") or row[col["fuel_litres"]] <= 0:
        return False
    row[col["fuel_litres"]] *= 2
    row[col["litres_per_meter_hour"]] *= 2
    return True


def _engine_without_meter(row: Row, col: Mapping[str, int], _med: FloatArray, _sd: FloatArray) -> bool:
    if not _has(row, col, "engine_hours", "meter_hours", "meter_vs_engine_gap") or row[col["engine_hours"]] < 1:
        return False
    row[col["meter_hours"]] = 0.0
    row[col["meter_vs_engine_gap"]] = row[col["engine_hours"]]
    if "litres_per_meter_hour" in col:
        row[col["litres_per_meter_hour"]] = np.nan  # undefined without meter hours, exactly as the feature would be
    return True


def _expense_spike(row: Row, col: Mapping[str, int], med: FloatArray, sd: FloatArray) -> bool:
    if not _has(row, col, "expense_total"):
        return False
    j = col["expense_total"]
    row[j] = row[j] * 3 + 3 * max(med[j], sd[j], 1.0)
    return True


def _off_site(row: Row, col: Mapping[str, int], med: FloatArray, sd: FloatArray) -> bool:
    if not _has(row, col, "outside_geofence_minutes", "km_travelled", "distinct_sites"):
        return False
    row[col["outside_geofence_minutes"]] += 600
    row[col["km_travelled"]] = row[col["km_travelled"]] * 3 + 3 * max(sd[col["km_travelled"]], 1.0)
    row[col["distinct_sites"]] += 2
    return True


def _cash_held(row: Row, col: Mapping[str, int], med: FloatArray, sd: FloatArray) -> bool:
    if not _has(row, col, "cash_outstanding"):
        return False
    j = col["cash_outstanding"]
    row[j] += 3 * max(sd[j], abs(med[j]), 1.0)
    return True


PERTURBATIONS: Mapping[Perturbation, _Apply] = {
    Perturbation.FUEL_DOUBLED: _fuel_doubled,
    Perturbation.ENGINE_WITHOUT_METER: _engine_without_meter,
    Perturbation.EXPENSE_SPIKE: _expense_spike,
    Perturbation.OFF_SITE_ACTIVITY: _off_site,
    Perturbation.CASH_HELD: _cash_held,
}


@dataclass(frozen=True, eq=False)
class InjectedSet:
    matrix: FeatureMatrix
    labels: BoolArray
    kinds: tuple[Perturbation | None, ...]


def inject_anomalies(matrix: FeatureMatrix, fraction: float, seed: int) -> InjectedSet:
    """Perturb a random `fraction` of rows in place (on a copy); kinds rotate and fall through if not applicable."""
    rng = np.random.default_rng(seed)
    values = matrix.values.copy()
    col = {c: i for i, c in enumerate(matrix.feature_codes)}
    with np.errstate(all="ignore"):
        finite = np.where(np.isfinite(values), values, np.nan)
        med = np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else 0.0 for c in finite.T])
        sd = np.array([np.std(c[np.isfinite(c)]) if np.isfinite(c).any() else 0.0 for c in finite.T])
    n_target = max(1, round(len(matrix) * fraction)) if len(matrix) else 0
    kinds_cycle = list(Perturbation)
    labels = np.zeros(len(matrix), dtype=np.bool_)
    kinds: list[Perturbation | None] = [None] * len(matrix)
    applied = 0
    for i in rng.permutation(len(matrix)):
        if applied >= n_target:
            break
        for offset in range(len(kinds_cycle)):
            kind = kinds_cycle[(applied + offset) % len(kinds_cycle)]
            row = values[i].copy()
            if PERTURBATIONS[kind](row, col, med, sd):
                values[i], labels[i], kinds[i] = row, True, kind
                applied += 1
                break
    return InjectedSet(matrix.with_values(values), labels, tuple(kinds))


def precision_recall_at_k(scores: FloatArray, labels: BoolArray, k: int) -> tuple[float, float]:
    """Rows ranked by score (NaN last, ties by position); returns (precision@k, recall@k)."""
    positives = int(labels.sum())
    if k <= 0 or positives == 0:
        return 0.0, 0.0
    ranked = np.argsort(-np.nan_to_num(scores, nan=-np.inf), kind="stable")[:k]
    hits = int(labels[ranked].sum())
    return hits / k, hits / positives


def alert_rate(calibrated_scores: FloatArray, threshold: float) -> float:
    finite = calibrated_scores[np.isfinite(calibrated_scores)]
    return float((finite >= threshold).mean()) if finite.size else math.nan


@dataclass(frozen=True, slots=True)
class ScorerMetrics:
    name: str
    recall_at_k: float
    precision_at_k: float
    k: int
    n_injected: int
    calibrated: bool
    alert_rate: float  # NaN when uncalibrated
    fold_recalls: tuple[float, ...]

    @property
    def recall_std(self) -> float:
        return float(np.std(self.fold_recalls)) if len(self.fold_recalls) >= 2 else math.nan

    def as_dict(self) -> dict[str, float]:
        d = asdict(self)
        return {
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "k": float(self.k),
            "n_injected": float(d["n_injected"]),
            "calibrated": float(self.calibrated),
            "alert_rate": self.alert_rate,
            "recall_fold_std": self.recall_std,
            "recall_fold_mean": float(np.mean(self.fold_recalls)) if self.fold_recalls else math.nan,
        }


def _concat(a: FeatureMatrix, b: FeatureMatrix) -> FeatureMatrix:
    return FeatureMatrix(a.tenant_id, a.feature_codes, a.keys + b.keys, np.vstack([a.values, b.values]))


def _fold_recalls(
    factory: Callable[[], AnomalyScorer], data: FeatureMatrix, purge: timedelta, folds: int, fraction: float, seed: int
) -> tuple[float, ...]:
    dates = sorted({k.as_of for k in data.keys})
    if folds < 1 or len(dates) < 4:
        return ()
    cuts = [dates[int(len(dates) * (0.4 + 0.5 * f / folds))] for f in range(folds + 1)]
    out: list[float] = []
    for f in range(folds):
        train_mask = np.array([k.as_of <= cuts[f] for k in data.keys])
        eval_mask = np.array([k.as_of - purge >= cuts[f] and k.as_of <= cuts[f + 1] for k in data.keys])
        if f == folds - 1:
            eval_mask = np.array([k.as_of - purge >= cuts[f] for k in data.keys])
        if train_mask.sum() < 5 or eval_mask.sum() < 5:
            continue
        scorer = factory().fit(data.take(train_mask))
        inj = inject_anomalies(data.take(eval_mask), fraction, seed + f + 1)
        k = int(inj.labels.sum())
        out.append(precision_recall_at_k(scorer.raw_scores(inj.matrix), inj.labels, k)[1])
    return tuple(out)


def evaluate_scorer(
    factory: Callable[[], AnomalyScorer],
    split: DatasetSplit,
    *,
    seed: int,
    injection_fraction: float = 0.1,
    alert_threshold: float = 0.98,
    folds: int = 3,
) -> tuple[AnomalyScorer, ScorerMetrics]:
    """Fit on train, calibrate on validation, measure on test; returns the fitted scorer and its metrics."""
    scorer = factory().fit(split.train)
    calibrated = scorer.calibrate(split.validation)
    injected = inject_anomalies(split.test, injection_fraction, seed)
    k = int(injected.labels.sum())
    precision, recall = precision_recall_at_k(scorer.raw_scores(injected.matrix), injected.labels, k)
    rate = math.nan
    if calibrated and scorer.calibrator is not None:
        rate = alert_rate(scorer.calibrator.transform(scorer.raw_scores(split.test)), alert_threshold)
    stability = _fold_recalls(
        factory, _concat(split.train, split.validation), split.config.purge, folds, injection_fraction, seed
    )
    return scorer, ScorerMetrics(scorer.name, recall, precision, k, k, calibrated, rate, stability)


@dataclass(frozen=True, slots=True)
class PromotionCriteria:
    """What a candidate must show before it may be proposed for approval beyond shadow mode."""

    min_recall_lift: float = 0.05  # candidate recall@k minus baseline recall@k
    max_alert_rate: float = 0.05  # on clean held-out rows at `alert_threshold`
    alert_threshold: float = 0.98  # calibrated percentile at which a row would be surfaced
    max_recall_std: float = 0.2  # across time folds
    min_injected: int = 5
    require_ready: bool = True


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    passed: bool
    metrics: Mapping[str, float]
    reasons: tuple[str, ...]


def evaluate_promotion(
    baseline: ScorerMetrics, candidate: ScorerMetrics, readiness: Readiness, criteria: PromotionCriteria
) -> EvaluationResult:
    metrics = {f"baseline.{k}": v for k, v in baseline.as_dict().items()}
    metrics |= {f"candidate.{k}": v for k, v in candidate.as_dict().items()}
    lift = candidate.recall_at_k - baseline.recall_at_k
    metrics["recall_lift"] = lift
    reasons: list[str] = []
    if criteria.require_ready and not readiness.ready:
        reasons.append("Tenant data is not READY: " + " ".join(readiness.reasons))
    if candidate.n_injected < criteria.min_injected:
        reasons.append(f"Only {candidate.n_injected} injected test anomalies; {criteria.min_injected} required.")
    if lift < criteria.min_recall_lift:
        reasons.append(
            f"Recall@k {candidate.recall_at_k:.2f} vs baseline {baseline.recall_at_k:.2f}; "
            f"lift {lift:+.2f} below required {criteria.min_recall_lift:+.2f}."
        )
    if not candidate.calibrated:
        reasons.append("Candidate is not calibrated; scores cannot be shown.")
    elif not candidate.alert_rate <= criteria.max_alert_rate:
        reasons.append(
            f"Alert rate {candidate.alert_rate:.3f} on clean held-out rows exceeds {criteria.max_alert_rate:.3f}."
        )
    std = candidate.recall_std
    if math.isnan(std):
        reasons.append("Not enough time folds to measure stability.")
    elif std > criteria.max_recall_std:
        reasons.append(f"Recall varies across time folds (std {std:.2f} > {criteria.max_recall_std:.2f}).")
    if reasons:
        return EvaluationResult(False, metrics, tuple(reasons))
    return EvaluationResult(True, metrics, (f"Candidate beats baseline recall@k by {lift:+.2f} within limits.",))
