from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from asseta.ml.features import (
    R1_FEATURE_DEFINITIONS,
    R1_FEATURES,
    CashDirection,
    CashEntry,
    EngineInterval,
    FeatureRegistry,
    FuelEntry,
    MachineFacts,
    MeterInterval,
    PositionSample,
    compute_snapshots,
)

AS_OF = datetime(2026, 3, 2, tzinfo=UTC)
DAY = timedelta(days=1)


def values(facts: MachineFacts, as_of: datetime = AS_OF) -> dict[str, float | None]:
    return {s.feature_code: s.value for s in compute_snapshots(R1_FEATURES, facts, as_of)}


def facts(**kw: object) -> MachineFacts:
    base = MachineFacts("t1", "M1", coverage_start=AS_OF - 30 * DAY)
    return replace(base, **kw)  # type: ignore[arg-type]


def test_late_recorded_row_is_excluded_until_it_arrives() -> None:
    on_time = MeterInterval(AS_OF - 3 * DAY, AS_OF - 3 * DAY + timedelta(hours=1), 8.0)
    late = MeterInterval(AS_OF - 2 * DAY, AS_OF + timedelta(hours=5), 6.0)  # happened in window, synced after as_of
    f = facts(meter=(on_time, late))
    assert values(f)["meter_hours"] == 8.0
    snap = next(s for s in compute_snapshots(R1_FEATURES, f, AS_OF) if s.feature_code == "meter_hours")
    assert snap.n_inputs == 1 and snap.data_cutoff == on_time.recorded_at
    assert values(f, AS_OF + DAY)["meter_hours"] == 14.0  # visible once recorded


def test_future_events_and_out_of_window_events_are_ignored() -> None:
    f = facts(
        meter=(
            MeterInterval(AS_OF + DAY, AS_OF - DAY, 5.0),  # event after as_of (clock skew) - ignored
            MeterInterval(AS_OF - 8 * DAY, AS_OF - 8 * DAY, 5.0),  # before the 7d window
            MeterInterval(AS_OF - DAY, AS_OF - DAY, 2.0),
        )
    )
    assert values(f)["meter_hours"] == 2.0


def test_none_not_zero_when_inputs_insufficient() -> None:
    v = values(facts())
    for code in (
        "meter_hours",
        "engine_hours",
        "meter_vs_engine_gap",
        "idle_engine_ratio",
        "km_travelled",
        "litres_per_meter_hour",
        "manual_capture_ratio",
        "distinct_sites",
        "outside_geofence_minutes",
    ):
        assert v[code] is None, code
    # additive features: covered window with no records is a genuine zero ...
    assert v["fuel_litres"] == 0.0 and v["expense_total"] == 0.0 and v["exceptions_count"] == 0.0
    # ... but before coverage started it is unknown
    uncovered = values(facts(coverage_start=AS_OF - 2 * DAY))
    assert uncovered["fuel_litres"] is None and uncovered["exceptions_count"] is None


def test_ratio_features_and_gap() -> None:
    t = AS_OF - DAY
    f = facts(
        meter=(MeterInterval(t, t, 10.0, manual=True), MeterInterval(t, t, 10.0)),
        engine=(EngineInterval(t, t, 24.0, idle_hours=6.0),),
        fuel=(FuelEntry(t, t, 300.0),),
        cash=(CashEntry(t, t, 1000.0, CashDirection.RECEIVED), CashEntry(t, t, 600.0, CashDirection.HANDED_OVER)),
    )
    v = values(f)
    assert v["litres_per_meter_hour"] == pytest.approx(15.0)
    assert v["meter_vs_engine_gap"] == pytest.approx(4.0)
    assert v["idle_engine_ratio"] == pytest.approx(0.25)
    assert v["manual_capture_ratio"] == pytest.approx(0.5)
    assert v["cash_outstanding"] == pytest.approx(400.0)
    tiny = values(facts(meter=(MeterInterval(t, t, 0.2),), fuel=(FuelEntry(t, t, 5.0),)))
    assert tiny["litres_per_meter_hour"] is None  # denominator too small to be meaningful


def test_spatial_features() -> None:
    t0 = AS_OF - DAY
    pts = (
        PositionSample(t0, t0, -15.0, 28.0, "A", True),
        PositionSample(t0 + timedelta(minutes=10), t0, -15.0, 28.01, "A", False),
        PositionSample(t0 + timedelta(hours=3), t0, -15.0, 28.02, "B", True),  # 170 min gap capped at 30
    )
    v = values(facts(positions=pts))
    assert v["km_travelled"] == pytest.approx(2 * 1.0735, rel=0.01)
    assert v["distinct_sites"] == 2.0
    assert v["outside_geofence_minutes"] == pytest.approx(30.0)


def test_feature_set_hash_is_stable_and_changes_on_version_bump() -> None:
    reordered = FeatureRegistry(tuple(reversed(R1_FEATURE_DEFINITIONS)))
    assert reordered.feature_set_hash() == R1_FEATURES.feature_set_hash()
    bumped = [replace(d, version=2) if d.code == "fuel_litres" else d for d in R1_FEATURE_DEFINITIONS]
    assert FeatureRegistry(bumped).feature_set_hash() != R1_FEATURES.feature_set_hash()
    assert len(R1_FEATURES.codes) == 13


def test_registry_rejects_duplicate_codes_and_definitions_are_immutable() -> None:
    with pytest.raises(ValueError, match="unique"):
        FeatureRegistry([R1_FEATURE_DEFINITIONS[0], R1_FEATURE_DEFINITIONS[0]])
    with pytest.raises(AttributeError):
        R1_FEATURE_DEFINITIONS[0].version = 9  # type: ignore[misc]
