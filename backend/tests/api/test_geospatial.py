"""Gate 2 (R1-D) acceptance: polygon/corridor geofences with tolerance, late/out-of-order replay, restricted
areas, unauthorized movement, fleet map status dimensions, stale handling, playback, proximity, connectivity."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.geospatial.connectivity import sweep_tenant
from asseta.tools.gps_simulator import Fix, route
from asseta.workers.connectivity_worker import sweep_all
from tests.support.api import Api
from tests.support.telemetry import DAR, Telemetry, Tracked

LAT, LON = DAR
D = 0.001  # ~111 m of latitude


def square(lat: float, lon: float, half: float) -> dict[str, Any]:
    ring = [
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
        [lon - half, lat - half],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def _at(api: Api, minutes: float, lat: float, lon: float = LON, speed: float = 0.0, **kw: Any) -> Fix:
    return Fix(api.clock.now + timedelta(minutes=minutes), lat, lon, speed, 0.0, **kw)


def _setup(api: Api, name: str, device: str) -> tuple[Telemetry, Tracked]:
    tel = Telemetry(api)
    a = tel.tracked_machine(name, device)
    r = a.owner.post(
        "/api/v1/tenant/geofences", {"name": "Site A yard", "kind": "ALLOWED_AREA", "polygon": square(LAT, LON, 2 * D)}
    )
    assert r.status_code == 201, r.text
    return tel, a


def _alerts(a: Tracked, **params: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = a.owner.get("/api/v1/tenant/alerts", **params).json()["items"]
    return items


def test_geofence_exit_with_tolerance_and_late_data_replay(api: Api) -> None:
    tel, a = _setup(api, "Fence Co", "FEN-1")
    edge = LAT + 2 * D  # polygon north edge
    tel.send("FEN-1", _at(api, 1, LAT))  # inside
    tel.send("FEN-1", _at(api, 2, edge + 0.0002))  # ~22 m outside: within 30 m tolerance band -> no exit
    tel.send("FEN-1", _at(api, 4, edge + 0.002))  # ~222 m outside -> EXIT
    tel.drain_timeline()
    events = a.owner.get(
        "/api/v1/tenant/geofence-events",
        **{"from": api.clock.now.isoformat(), "to": (api.clock.now + timedelta(hours=1)).isoformat()},
    )
    assert [e["transition"] for e in events.json()] == ["ENTER", "EXIT"]
    [exit_alert] = _alerts(a, alert_type="GEOFENCE_EXIT")
    assert exit_alert["evidence"]["distance_outside_m"] > 30 and exit_alert["policy_version"].startswith("TRACKING@")

    # A buffered position arrives late: the machine had already left at minute 3. Replay moves the EXIT earlier
    # and the minute-4 alert is SUPERSEDED (kept for audit), not deleted.
    tel.send("FEN-1", _at(api, 3, edge + 0.003))
    tel.drain_timeline()
    events = a.owner.get(
        "/api/v1/tenant/geofence-events",
        **{"from": api.clock.now.isoformat(), "to": (api.clock.now + timedelta(hours=1)).isoformat()},
    )
    exits = [e for e in events.json() if e["transition"] == "EXIT"]
    assert len(exits) == 1 and exits[0]["event_time"].startswith(_at(api, 3, 0).time.isoformat()[:16])
    by_status = {x["status"]: x for x in _alerts(a, alert_type="GEOFENCE_EXIT")}
    assert set(by_status) == {"OPEN", "SUPERSEDED"}
    tel.drain_timeline()  # idempotent: nothing pending, nothing changes
    assert len(_alerts(a, alert_type="GEOFENCE_EXIT")) == 2


def test_corridor_restricted_area_and_unauthorized_movement(api: Api) -> None:
    tel, a = _setup(api, "Corridor Co", "COR-1")
    corridor = {
        "name": "Haul road",
        "kind": "SITE_BOUNDARY",
        "corridor_width_m": 100,
        "corridor": {"type": "LineString", "coordinates": [[LON, LAT], [LON + 10 * D, LAT]]},
    }
    r = a.owner.post("/api/v1/tenant/geofences", corridor)
    assert r.status_code == 201 and 90_000 < r.json()["area_m2"] < 130_000, r.json()  # ~1.1 km x 100 m
    a.owner.post(
        "/api/v1/tenant/geofences",
        {"name": "Fuel depot", "kind": "RESTRICTED_AREA", "polygon": square(LAT - 5 * D, LON, D)},
    )
    # Approved operating window 06:00-18:00 Africa/Dar_es_Salaam (UTC+3); clock is 12:00 local.
    pol = a.owner.post(
        "/api/v1/tenant/policies/TRACKING/versions",
        {
            "scope": "TENANT",
            "values": {"operating_window_start": "06:00", "operating_window_end": "18:00"},
            "reason": "Site hours",
        },
    )
    assert pol.status_code == 201, pol.text
    tel.send("COR-1", _at(api, 1, LAT, LON + 5 * D, speed=20))  # on corridor, in hours
    tel.send("COR-1", _at(api, 2, LAT - 5 * D, speed=10))  # enters restricted depot
    late_fix = _at(api, 60 * 7, LAT, speed=25)  # 19:00 local, moving -> unauthorized
    api.clock.now = late_fix.time + timedelta(seconds=2)
    tel.send("COR-1", late_fix)
    tel.drain_timeline()
    types = {x["alert_type"] for x in _alerts(a)}
    assert {"RESTRICTED_AREA_ENTRY", "UNAUTHORIZED_MOVEMENT"} <= types
    [mv] = _alerts(a, alert_type="UNAUTHORIZED_MOVEMENT")
    assert mv["severity"] == "CRITICAL" and mv["evidence"]["local_time"].startswith("2026-11-01T19:")


def test_fleet_map_status_dimensions_staleness_and_history(api: Api) -> None:
    tel, a = _setup(api, "Map Co", "MAP-1")
    fixes = route([(LAT, LON), (LAT + D, LON + D)], api.clock.now + timedelta(minutes=1), 12.0, 30, dwell_points=12)
    for f in fixes:
        api.clock.now = f.time + timedelta(seconds=2)  # realistic delivery: received ~2 s after the fix
        tel.send("MAP-1", f, include_ignition=False)  # tracker never reports ignition
    tel.drain_timeline()
    api.clock.now = fixes[-1].time + timedelta(seconds=30)
    [m] = a.owner.get("/api/v1/tenant/fleet/map").json()
    assert m["connectivity"] == "LIVE" and m["is_live"] and m["observed_motion"] == "STATIONARY"
    assert m["observed_engine"] == "UNKNOWN"  # ignition capability never verified -> no engine claim
    assert m["reported_work_status"] == "NO_ACTIVE_JOB" and m["location_compliance"] == "COMPLIANT"
    assert m["position_source"] == "TRACKER:MAP-1" and m["accuracy_m"] == 5.0

    api.clock.now += timedelta(hours=2)
    [m] = a.owner.get("/api/v1/tenant/fleet/map").json()
    assert m["connectivity"] == "STALE" and not m["is_live"]
    assert m["observed_motion"] == "UNKNOWN" and m["location_compliance"] == "UNKNOWN"  # no claims on stale data
    assert m["last_seen_age_seconds"] >= 7200

    h = a.owner.get(
        f"/api/v1/tenant/fleet/machines/{a.machine_id}/history",
        **{"from": fixes[0].time.isoformat(), "to": (fixes[-1].time + timedelta(minutes=1)).isoformat()},
    ).json()
    assert len(h["points"]) == len(fixes) and 0.1 < h["distance_km"] < 0.3
    assert len(h["stops"]) == 1 and h["stops"][0]["duration_seconds"] >= 300
    near = a.owner.get("/api/v1/tenant/fleet/nearby", lon=LON + D, lat=LAT + D, radius_m=50).json()
    assert [n["machine_id"] for n in near] == [a.machine_id]

    other = api.onboard("Other Co", price="1")
    assert other["owner"].get("/api/v1/tenant/fleet/map").json() == []
    hist = other["owner"].get(
        f"/api/v1/tenant/fleet/machines/{a.machine_id}/history",
        **{"from": fixes[0].time.isoformat(), "to": fixes[-1].time.isoformat()},
    )
    assert hist.status_code == 404


def test_connectivity_sweeper_stale_offline_and_recovery(api: Api) -> None:
    tel, a = _setup(api, "Conn Co", "CON-1")
    tenant_id = a.tenant["tenant"]["id"]
    tel.send("CON-1", _at(api, 0, LAT))

    def sweep(minutes_after: float) -> None:
        with get_sessionmaker().begin() as s:
            apply_scope(s, DbScope.TENANT, tenant_id, None)
            sweep_tenant(s, tenant_id, api.clock.now + timedelta(minutes=minutes_after))

    sweep(1)
    sweep(45)  # > 30 min stale threshold
    sweep(60 * 7)  # > 6 h offline threshold
    types = {(x["alert_type"], x["status"]) for x in _alerts(a)}
    assert ("TRACKER_STALE", "OPEN") in types and ("TRACKER_OFFLINE", "OPEN") in types
    api.clock.now += timedelta(hours=7)
    tel.send("CON-1", _at(api, 0, LAT))
    sweep(1)
    assert {x["status"] for x in _alerts(a) if x["alert_type"].startswith("TRACKER_")} == {"RESOLVED"}
    sub = api.platform.get(f"/api/v1/platform/tenants/{tenant_id}/subscription").json()
    assert sub["enrolled_assets"] == 1  # offline hardware never removes an asset from billing


def test_worker_sweep_runs_as_runtime_role(api: Api) -> None:
    """The worker's full sweep (partition top-up included) works as asseta_app, which has no CREATE on the schema."""
    tel, a = _setup(api, "Sweep Co", "SWP-1")
    tel.send("SWP-1", _at(api, 0, LAT))
    with get_sessionmaker().begin() as s:
        s.execute(text("SELECT ensure_telemetry_partitions(3, 0)"))
        s.execute(text("SELECT ensure_telemetry_partitions(3, 0)"))  # idempotent
        with pytest.raises(DBAPIError, match="between 0 and 24"), s.begin_nested():
            s.execute(text("SELECT ensure_telemetry_partitions(1000, 0)"))
    assert uuid.UUID(a.tenant["tenant"]["id"]) in sweep_all()


def test_policy_hierarchy_overrides_and_guards(api: Api) -> None:
    tel, a = _setup(api, "Policy Co", "POL-1")
    eff = a.owner.get("/api/v1/tenant/policies/TRACKING/effective").json()
    assert eff["version_stamp"] == "TRACKING@P1" and eff["values"]["stale_after_seconds"] == 1800
    a.owner.post(
        "/api/v1/tenant/policies/TRACKING/versions",
        {"scope": "TENANT", "values": {"stale_after_seconds": 900}, "reason": "Tighter"},
    )
    m = a.owner.post(
        "/api/v1/tenant/policies/TRACKING/versions",
        {
            "scope": "MACHINE",
            "scope_ref_id": a.machine_id,
            "values": {"stale_after_seconds": 3600},
            "reason": "Remote site",
        },
    )
    assert m.status_code == 201
    eff = a.owner.get("/api/v1/tenant/policies/TRACKING/effective", machine_id=a.machine_id).json()
    assert eff["version_stamp"] == "TRACKING@P1.T1.M1" and eff["values"]["stale_after_seconds"] == 3600
    bad_field = a.owner.post(
        "/api/v1/tenant/policies/TRACKING/versions",
        {"scope": "MACHINE", "scope_ref_id": a.machine_id, "values": {"moving_speed_kmh": 9}, "reason": "nope"},
    )
    assert bad_field.json()["error"]["code"] == "POLICY_FIELD_NOT_OVERRIDABLE"
    bad_order = a.owner.post(
        "/api/v1/tenant/policies/TRACKING/versions",
        {"scope": "TENANT", "values": {"stale_after_seconds": 99999}, "reason": "beyond offline"},
    )
    assert bad_order.json()["error"]["code"] == "POLICY_INVALID"
    other = api.onboard("Policy Other", price="1")
    foreign = other["owner"].post(
        "/api/v1/tenant/policies/TRACKING/versions",
        {"scope": "MACHINE", "scope_ref_id": a.machine_id, "values": {"stale_after_seconds": 600}, "reason": "probe"},
    )
    assert foreign.status_code == 404, foreign.text  # cannot target another tenant machine
    platform = a.owner.post(
        "/api/v1/tenant/policies/TRACKING/versions", {"scope": "PLATFORM", "values": {}, "reason": "escalate"}
    )
    assert platform.json()["error"]["code"] == "POLICY_SCOPE"
    # positions record the policy version they were evaluated under
    tel.send("POL-1", _at(api, 1, LAT))
    h = a.owner.get(
        f"/api/v1/tenant/fleet/machines/{a.machine_id}/history",
        **{"from": api.clock.now.isoformat(), "to": (api.clock.now + timedelta(hours=1)).isoformat()},
    ).json()
    assert h["policy_version"] == "TRACKING@P1.T1.M1"
