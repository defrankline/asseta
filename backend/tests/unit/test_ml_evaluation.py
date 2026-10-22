import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from asseta.ml.datasets import FeatureMatrix, ReadinessStatus, RowKey, SufficiencyCriteria, assess_readiness
from asseta.ml.drift import DriftLevel, feature_drift, level_for, psi
from asseta.ml.evaluation import (
    Perturbation,
    PromotionCriteria,
    ScorerMetrics,
    evaluate_promotion,
    inject_anomalies,
    precision_recall_at_k,
)
from asseta.ml.features import R1_FEATURES

T0 = datetime(2026, 1, 5, tzinfo=UTC)


def matrix(n: int = 200, shift: float = 0.0, seed: int = 0) -> FeatureMatrix:
    rng = np.random.default_rng(seed)
    codes = R1_FEATURES.codes
    keys = tuple(RowKey(T0 + timedelta(days=7 * (i // 10)), f"M{i % 10}") for i in range(n))
    return FeatureMatrix("t1", codes, keys, rng.normal(20 + shift, 4, (n, len(codes))))


def metrics(
    name: str,
    recall: float,
    alert: float = 0.02,
    folds: tuple[float, ...] = (0.6, 0.65, 0.7),
    calibrated: bool = True,
    injected: int = 10,
) -> ScorerMetrics:
    return ScorerMetrics(name, recall, recall, injected, injected, calibrated, alert, folds)


READY = assess_readiness(matrix(), SufficiencyCriteria(min_machines=5, min_machine_weeks=20, min_weeks_history=4))


def test_precision_recall_at_k() -> None:
    scores = np.array([0.9, 0.1, 0.8, np.nan, 0.7])
    labels = np.array([True, False, False, True, True])
    assert precision_recall_at_k(scores, labels, 2) == pytest.approx((0.5, 1 / 3))
    assert precision_recall_at_k(scores, labels, 3) == pytest.approx((2 / 3, 2 / 3))
    assert precision_recall_at_k(scores, np.zeros(5, dtype=bool), 2) == (0.0, 0.0)


def test_injection_is_deterministic_labelled_and_documented() -> None:
    m = matrix(100)
    a, b = inject_anomalies(m, 0.1, seed=3), inject_anomalies(m, 0.1, seed=3)
    assert a.labels.sum() == 10 and np.array_equal(a.labels, b.labels)
    assert np.array_equal(a.matrix.values, b.matrix.values, equal_nan=True)
    assert np.array_equal(a.matrix.values[~a.labels], m.values[~a.labels])  # clean rows untouched
    assert {k for k in a.kinds if k is not None} == set(Perturbation)
    i = next(i for i, k in enumerate(a.kinds) if k is Perturbation.FUEL_DOUBLED)
    assert a.matrix.column("fuel_litres")[i] == pytest.approx(2 * m.column("fuel_litres")[i])
    j = next(i for i, k in enumerate(a.kinds) if k is Perturbation.ENGINE_WITHOUT_METER)
    assert a.matrix.column("meter_hours")[j] == 0.0 and math.isnan(a.matrix.column("litres_per_meter_hour")[j])


def test_promotion_passes_when_candidate_beats_baseline_within_limits() -> None:
    result = evaluate_promotion(metrics("b", 0.5), metrics("c", 0.7), READY, PromotionCriteria())
    assert result.passed and result.metrics["recall_lift"] == pytest.approx(0.2)
    assert "candidate.alert_rate" in result.metrics and "baseline.recall_at_k" in result.metrics


@pytest.mark.parametrize(
    ("candidate", "fragment"),
    [
        (metrics("c", 0.52), "lift"),
        (metrics("c", 0.9, alert=0.2), "Alert rate"),
        (metrics("c", 0.9, folds=(0.1, 0.9)), "time folds"),
        (metrics("c", 0.9, calibrated=False, alert=math.nan), "not calibrated"),
        (metrics("c", 0.9, injected=2), "injected"),
    ],
)
def test_promotion_fails_with_specific_reason(candidate: ScorerMetrics, fragment: str) -> None:
    result = evaluate_promotion(metrics("b", 0.5), candidate, READY, PromotionCriteria())
    assert not result.passed
    assert any(fragment in r for r in result.reasons)


def test_promotion_requires_ready_data() -> None:
    not_ready = assess_readiness(None, SufficiencyCriteria())
    assert not_ready.status is ReadinessStatus.INSUFFICIENT_DATA
    result = evaluate_promotion(metrics("b", 0.1), metrics("c", 0.9), not_ready, PromotionCriteria())
    assert not result.passed and "not READY" in result.reasons[0]


def test_psi_near_zero_for_same_distribution_and_high_for_shift() -> None:
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 5000), rng.normal(0, 1, 5000)
    assert psi(a, b) < 0.02
    assert psi(a, rng.normal(1.5, 1, 5000)) > 0.25
    missing = b.copy()
    missing[:2500] = np.nan  # half the values suddenly missing is drift too
    assert psi(a, missing) > 0.25
    assert level_for(0.05) is DriftLevel.STABLE and level_for(0.15) is DriftLevel.WATCH
    assert level_for(0.3) is DriftLevel.DRIFT and level_for(None) is DriftLevel.INSUFFICIENT_DATA


def test_feature_drift_report() -> None:
    train = matrix(3000, seed=1)
    same = feature_drift(train, matrix(3000, seed=2))
    assert same.level is DriftLevel.STABLE and "0 drifted" in same.summary
    v = matrix(3000, seed=2).values.copy()
    v[:, 0] += 8
    shifted = feature_drift(train, matrix(3000, seed=2).with_values(v))
    assert shifted.level is DriftLevel.DRIFT and shifted.features[0].level is DriftLevel.DRIFT
    assert train.feature_codes[0] in shifted.summary
    tiny = feature_drift(train, matrix(10, seed=2))
    assert tiny.level is DriftLevel.INSUFFICIENT_DATA
