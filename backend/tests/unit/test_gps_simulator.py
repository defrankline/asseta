"""Deterministic GPS simulator: a parked machine reports its engine off (demo fleets must not look always-on)."""

from datetime import UTC, datetime

from asseta.tools.gps_simulator import route

START = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
LEG = [(-6.8390, 39.3060), (-6.8370, 39.3080)]


def test_default_route_keeps_engine_running_while_dwelling() -> None:
    fixes = route(LEG, START, 6.0, 12, dwell_points=2, hours_start_ms=0)
    assert all(f.ignition for f in fixes)


def test_park_engine_off_stops_ignition_and_engine_hours_after_arrival() -> None:
    fixes = route(LEG, START, 6.0, 12, dwell_points=2, park_engine_off=True, hours_start_ms=0)
    moving, arrival, parked = fixes[:-3], fixes[-3], fixes[-2:]
    assert all(f.ignition and f.speed_kmh > 0 for f in moving)
    assert arrival.ignition is True and arrival.speed_kmh == 0.0
    assert [f.ignition for f in parked] == [False, False]
    assert arrival.hours_ms is not None
    assert {f.hours_ms for f in parked} == {arrival.hours_ms + 12_000}  # hours stop once the engine is off
    assert [f.time for f in fixes] == sorted(f.time for f in fixes)
