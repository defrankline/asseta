"""Gate 2 (R1-C) acceptance: tracker registry, anti-spoofing, capability verification, enrollment gate,
tracker swap without double billing, and authenticated, quarantining, dedupe-safe, event-time-correct ingestion."""

from datetime import timedelta

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.tools.gps_simulator import Fix
from tests.support.api import Api
from tests.support.telemetry import DAR, Telemetry


def _fix(
    api: Api,
    minutes: float,
    lat: float = DAR[0],
    lon: float = DAR[1],
    *,
    ignition: bool | None = True,
    valid: bool = True,
    alarm: str | None = None,
) -> Fix:
    return Fix(
        api.clock.now + timedelta(minutes=minutes), lat, lon, 0.0, 0.0, ignition=ignition, valid=valid, alarm=alarm
    )


def test_spoofing_enrollment_gate_and_provisioning(api: Api) -> None:
    tel = Telemetry(api)
    a = tel.tracked_machine("Track A", "DEV-A1")
    b = api.onboard("Track B", price="1000")
    api.activate(b)
    dup = b["owner"].post(
        "/api/v1/tenant/trackers", {"tracker_model_id": tel.model_id, "external_id": "DEV-A1", "label": "stolen id"}
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "TRACKER_EXTERNAL_ID_UNAVAILABLE"

    # An unenrolled machine cannot be tracked (DEC-014).
    m = b["owner"].post("/api/v1/tenant/machines", {"asset_code": "UNB-1", "name": "Unbilled"}).json()["id"]
    tid = tel.register(b["owner"], "DEV-B1")
    r = b["owner"].post(
        f"/api/v1/tenant/trackers/{tid}/assign", {"machine_id": m, "effective_from": api.clock.now.isoformat()}
    )
    assert r.json()["error"]["code"] == "MACHINE_NOT_ENROLLED"

    t = a.owner.get(f"/api/v1/tenant/trackers/{a.tracker_id}").json()
    assert t["provisioning_state"] == "REGISTERED"
    caps = {c["capability"]: c for c in t["capabilities"]}
    assert caps["IGNITION"]["declared"] and caps["IGNITION"]["verified_at"] is None
    assert not caps["FUEL_LEVEL"]["declared"]
    assert tel.send("DEV-A1", _fix(api, 1, ignition=True))["accepted"] == 1
    t = a.owner.get(f"/api/v1/tenant/trackers/{a.tracker_id}").json()
    caps = {c["capability"]: c for c in t["capabilities"]}
    assert t["provisioning_state"] == "VERIFIED_REPORTING"
    assert caps["IGNITION"]["verified_at"] is not None and caps["ENGINE_HOURS"]["verified_at"] is None


def test_tracker_swap_keeps_one_billable_asset_and_attaches_late_data_by_event_time(api: Api) -> None:
    tel = Telemetry(api)
    a = tel.tracked_machine("Swap Co", "OLD-1")
    new_id = tel.register(a.owner, "NEW-1")
    swap_at = api.clock.now + timedelta(hours=2)
    conflict = a.owner.post(
        f"/api/v1/tenant/trackers/{new_id}/assign", {"machine_id": a.machine_id, "effective_from": swap_at.isoformat()}
    )
    assert conflict.json()["error"]["code"] == "PRIMARY_TRACKER_EXISTS"
    r = a.owner.post(
        f"/api/v1/tenant/trackers/{new_id}/assign",
        {
            "machine_id": a.machine_id,
            "effective_from": swap_at.isoformat(),
            "replace_existing_primary": True,
            "reason": "Old unit failed",
        },
    )
    assert r.status_code == 201, r.text
    api.clock.set(api.clock.now.date())  # keep "today" for billing
    # Billing: still exactly one billable asset; invoice has one asset line.
    sub = api.platform.get(f"/api/v1/platform/tenants/{a.tenant['tenant']['id']}/subscription").json()
    assert sub["enrolled_assets"] == 1
    inv = api.generate(sub["id"], api.clock.now.date())["created"][0]
    assert [line["line_type"] for line in inv["lines"]] == ["ASSET_SUBSCRIPTION"]

    api.clock.now = swap_at + timedelta(hours=1)
    late_old = tel.send("OLD-1", Fix(swap_at - timedelta(minutes=30), DAR[0], DAR[1], 0, 0))  # buffered upload
    assert late_old["accepted"] == 1
    after_swap_old = tel.send("OLD-1", Fix(swap_at + timedelta(minutes=10), DAR[0], DAR[1], 0, 0))
    assert after_swap_old["reasons"] == ["UNASSIGNED"]
    assert tel.send("NEW-1", Fix(swap_at + timedelta(minutes=20), DAR[0], DAR[1], 0, 0))["accepted"] == 1


def test_ingestion_auth_quarantine_dedupe_and_ordering(api: Api) -> None:
    tel = Telemetry(api)
    a = tel.tracked_machine("Ingest Co", "ING-1")
    bad = api.client.post("/api/v1/telemetry/traccar", json={}, headers={"X-Asseta-Gateway-Key": "nope"})
    assert bad.status_code == 401
    assert api.client.post("/api/v1/telemetry/traccar", json={}).status_code == 401

    assert tel.raw({"position": "garbage"})["reasons"] == ["MALFORMED"]
    assert tel.send("NOBODY-1", _fix(api, 1))["reasons"] == ["UNKNOWN_DEVICE"]
    assert tel.send("ING-1", _fix(api, 30))["reasons"] == ["CLOCK_FUTURE"]
    assert tel.send("ING-1", _fix(api, -60 * 24 * 40))["reasons"] == ["UNASSIGNED"]  # before installation

    t2 = _fix(api, 2, lat=DAR[0] + 0.001)
    assert tel.send("ING-1", t2)["accepted"] == 1
    assert tel.send("ING-1", t2)["duplicates"] == 1  # replay of the same message
    t1 = _fix(api, 1)
    assert tel.send("ING-1", t1)["accepted"] == 1  # out-of-order (late) delivery
    status = a.owner.get(f"/api/v1/tenant/fleet/machines/{a.machine_id}").json()
    assert status["position_time"].startswith(t2.time.isoformat()[:19])  # late data never overwrites newer
    assert tel.send("ING-1", _fix(api, 3, valid=False))["accepted"] == 1  # heartbeat without fix

    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, a.tenant["tenant"]["id"], None)
        rows = s.execute(text("SELECT event_time, is_late FROM machine_position_event ORDER BY event_time")).all()
        assert [r.is_late for r in rows] == [True, False]
        outcomes: dict[str, int] = dict(
            s.execute(text("SELECT status, count(*) FROM tracker_ingestion_event GROUP BY status")).all()
        )
        assert outcomes == {"ACCEPTED": 2, "DUPLICATE": 1, "ACCEPTED_NO_FIX": 1, "QUARANTINED": 2}  # tenant-visible
        # unresolved device / malformed rows are system-only (no tenant), invisible to the tenant
    start = api.clock.now
    api.clock.now = start + timedelta(days=40)  # within the assignment but beyond the 30-day replay window
    assert tel.send("ING-1", Fix(start + timedelta(minutes=5), DAR[0], DAR[1], 0, 0))["reasons"] == ["TOO_OLD"]
    events = a.owner.get("/api/v1/tenant/telemetry/ingestion-events", status="QUARANTINED").json()
    assert {e["quarantine_reason"] for e in events["items"]} == {"CLOCK_FUTURE", "UNASSIGNED", "TOO_OLD"}

    # Original telemetry is immutable even for the application role.
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        try:
            s.execute(text("UPDATE machine_position_event SET speed_kmh = 99"))
            raise AssertionError("telemetry mutated")
        except Exception as exc:
            assert "permission denied" in str(exc) or "immutable" in str(exc)


def test_unenrolled_machine_data_is_quarantined_and_tamper_alerts(api: Api) -> None:
    tel = Telemetry(api)
    a = tel.tracked_machine("Unenroll Co", "UNE-1")
    tel.send("UNE-1", _fix(api, 1, alarm="tampering"))
    alerts = a.owner.get("/api/v1/tenant/alerts", alert_type="TAMPER").json()
    assert alerts["total"] == 1 and alerts["items"][0]["severity"] == "CRITICAL"
    sid = api.platform.get(f"/api/v1/platform/tenants/{a.tenant['tenant']['id']}/subscription").json()["id"]
    [enr] = api.platform.get(f"/api/v1/platform/subscriptions/{sid}/enrollments").json()
    tomorrow = (api.clock.now + timedelta(days=1)).date().isoformat()
    a.owner.post(
        f"/api/v1/tenant/billing/enrollments/{enr['id']}/end",
        {"effective_to": tomorrow, "reason": "REMOVED_FROM_FLEET"},
    )
    out = tel.send("UNE-1", Fix(api.clock.now + timedelta(days=1, minutes=1), DAR[0], DAR[1], 0, 0))
    assert out["reasons"] in (["NOT_ENROLLED"], ["CLOCK_FUTURE"])  # future relative to clock: guard both
    api.clock.now = api.clock.now + timedelta(days=1, minutes=5)
    out = tel.send("UNE-1", Fix(api.clock.now - timedelta(minutes=1), DAR[0], DAR[1], 0, 0))
    assert out["reasons"] == ["NOT_ENROLLED"]
