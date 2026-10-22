import re
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from asseta.ml.baseline import (
    RobustZScoreBaseline,
    cashflow_trend_insight,
    fuel_efficiency_insight,
    utilization_insight,
)
from asseta.ml.datasets import FeatureMatrix, ReadinessStatus, RowKey
from asseta.ml.models import CalibrationError, Direction, EmpiricalCalibrator, IsolationForestModel

T0 = datetime(2026, 1, 5, tzinfo=UTC)
CODES = ("fuel_litres", "litres_per_meter_hour", "meter_hours")


def fleet(n_machines: int = 6, periods: int = 20, seed: int = 0) -> FeatureMatrix:
    rng = np.random.default_rng(seed)
    keys, rows = [], []
    for p in range(periods):
        for m in range(n_machines):
            meter = 40 + m * 5 + rng.normal(0, 2)
            lpmh = 10 + m + rng.normal(0, 0.5)
            keys.append(RowKey(T0 + timedelta(days=7 * p), f"M{m}"))
            rows.append([lpmh * meter, lpmh, meter])
    return FeatureMatrix("t1", CODES, tuple(keys), np.array(rows))


def with_anomaly(m: FeatureMatrix, row: int) -> FeatureMatrix:
    v = m.values.copy()
    v[row, 0] *= 2.4
    v[row, 1] *= 2.4
    return m.with_values(v)


def test_baseline_flags_injected_fuel_anomaly_with_neutral_explanation() -> None:
    train, test = fleet(seed=0), with_anomaly(fleet(periods=4, seed=1), 7)
    model = RobustZScoreBaseline().fit(train)
    scores = model.raw_scores(test)
    assert int(np.nanargmax(scores)) == 7
    row = model.score(test)[7]
    assert row.contributions[0].direction is Direction.ABOVE
    assert row.contributions[0].feature in {"fuel_litres", "litres_per_meter_hour"}
    assert row.contributions[0].reference_scope == "machine"
    assert re.search(r"\d\.\dx this machine's median", row.explanations[0])


def test_baseline_handles_all_missing_rows_and_constant_features() -> None:
    train = fleet()
    v = train.values.copy()
    v[:, 2] = 50.0  # constant per machine -> MAD 0, floor prevents division blow-up
    model = RobustZScoreBaseline().fit(train.with_values(v))
    test = fleet(periods=1, seed=3)
    tv = test.values.copy()
    tv[0, :] = np.nan
    tv[1, 2] = 51.0
    scored = model.score(test.with_values(tv))
    assert scored[0].raw_score is None and scored[0].contributions == () and not scored[0].calibrated
    assert all(np.isfinite(model.raw_scores(test.with_values(tv))[1:]))


def test_isolation_forest_is_deterministic_with_seed() -> None:
    train, test = fleet(), with_anomaly(fleet(periods=3, seed=2), 4)
    a = IsolationForestModel(random_state=11).fit(train).raw_scores(test)
    b = IsolationForestModel(random_state=11).fit(train).raw_scores(test)
    c = IsolationForestModel(random_state=12).fit(train).raw_scores(test)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert int(np.argmax(a)) == 4


def test_isolation_forest_standardization_fitted_on_train_only() -> None:
    train = fleet()
    model = IsolationForestModel(random_state=0, per_entity_centering=False).fit(train)
    assert model.scaler is not None
    expected_mean = np.mean(train.values, axis=0)
    assert np.allclose(model.scaler.mean_, expected_mean)
    model.raw_scores(fleet(periods=2, seed=9))  # scoring does not refit
    assert np.allclose(model.scaler.mean_, expected_mean)


def test_calibration_monotone_bounded_and_flag_semantics() -> None:
    cal = EmpiricalCalibrator(np.linspace(0, 1, 50))
    out = cal.transform(np.array([-5.0, 0.0, 0.3, 0.6, 1.0, 9.0]))
    assert np.all(np.diff(out) >= 0) and out.min() >= 0 and out.max() <= 1
    assert out[0] == 0.0 and out[-1] == 1.0
    with pytest.raises(CalibrationError):
        EmpiricalCalibrator(np.arange(5.0))

    model = RobustZScoreBaseline().fit(fleet())
    uncal = model.score(fleet(periods=1, seed=4))
    assert all(r.score is None and not r.calibrated and r.raw_score is not None for r in uncal)
    assert not model.calibrate(fleet(periods=1, seed=5))  # 6 rows < 20 -> stays uncalibrated
    assert model.calibrate(fleet(periods=5, seed=5))
    cal_rows = model.score(fleet(periods=1, seed=4))
    assert all(r.calibrated and r.score is not None and 0 <= r.score <= 1 for r in cal_rows)


def test_explanations_never_use_accusatory_language() -> None:
    train, test = fleet(), with_anomaly(fleet(periods=4, seed=1), 3)
    for model in (RobustZScoreBaseline().fit(train), IsolationForestModel(random_state=0).fit(train)):
        for row in model.score(test, top_k=3):
            for text in row.explanations:
                lowered = text.lower()
                assert not any(w in lowered for w in ("fraud", "theft", "stole", "suspect", "guilty")), text


def test_baseline_insights_return_insufficient_data_with_minimums() -> None:
    low = fuel_efficiency_insight([10.0, None, 11.0], 12.0, min_weeks=4)
    assert low.status is ReadinessStatus.INSUFFICIENT_DATA and low.value is None and low.min_required == 4
    ok = fuel_efficiency_insight([10.0, 10.0, 12.0, 10.0], 20.0)
    assert ok.status is ReadinessStatus.READY and ok.reference == 10.0 and "2.0x" in ok.message
    assert utilization_insight([30.0, 32.0], 12).status is ReadinessStatus.INSUFFICIENT_DATA
    assert utilization_insight([30.0] * 4, 24).value == pytest.approx(5.0)
    trend = cashflow_trend_insight([100, 110, 120, 130, 140, 150])
    assert trend.value == pytest.approx(10.0) and "improving" in trend.message
