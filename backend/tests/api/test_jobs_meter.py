"""Gate 3 acceptance (prompt.md §10 #5 and R1-E)."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.tools.gps_simulator import Fix, traccar_payload
from tests.support.api import Actor, Api
from tests.support.jobs import capture, fix, new_job, photo, setup_job
from tests.support.telemetry import DAR


def _submit(api: Api, actor: Actor, body: dict[str, Any]) -> dict[str, Any]:
    r = actor.post("/api/v1/tenant/meter-captures", body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def _types(result: dict[str, Any]) -> set[str]:
    return {f["type"] for f in result["findings"]}


def _policy(actor: Actor, values: dict[str, Any], scope: str = "TENANT", ref: str | None = None) -> None:
    r = actor.post(
        "/api/v1/tenant/policies/METER_CAPTURE/versions",
        {"scope": scope, "scope_ref_id": ref, "values": values, "reason": "Owner capture rules"},
    )
    assert r.status_code == 201, r.text


def test_auto_open_manual_close_full_job_and_billable_hours(api: Api) -> None:
    c = setup_job(api)
    o, now = c.owner, api.clock.now
    _policy(o, {"opening_mode": "AUTOMATIC", "closing_mode": "MANUAL", "manual_photo_required": False})
    assert (
        o.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "START"}).json()["error"]["code"]
        == "OPENING_REQUIRED"
    )
    opening = _submit(api, o, capture(c.job_id, "OPENING", "1200.0", now, photo_id=photo(api, o)))
    assert opening["capture"]["state"] == "ACCEPTED" and opening["findings"] == []
    assert opening["capture"]["policy_version"].startswith("METER_CAPTURE@P1.T1")
    o.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "START"})
    o.post(
        f"/api/v1/tenant/jobs/{c.job_id}/activities",
        {
            "client_id": "6f1c2a8e-0000-4000-8000-000000000001",
            "activity_type": "DOWNTIME",
            "started_at": (now + timedelta(hours=2)).isoformat(),
            "ended_at": (now + timedelta(hours=3, minutes=30)).isoformat(),
            "note": "Hydraulic hose replaced",
        },
    )
    later = now + timedelta(hours=9)
    api.clock.set_at(later)
    closing = _submit(api, o, capture(c.job_id, "CLOSING", "1208.0", later, mode="MANUAL"))
    assert closing["capture"]["state"] == "ACCEPTED", closing
    assert (
        o.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "COMPLETE"}).json()["error"]["code"]
        == "ACK_REQUIRED"
    )
    o.post(
        f"/api/v1/tenant/jobs/{c.job_id}/acknowledgements",
        {
            "client_id": "6f1c2a8e-0000-4000-8000-000000000002",
            "method": "NAME_CONFIRMATION",
            "signer_name": "Site Engineer",
            "acknowledged_hours": "6.5",
            "captured_at": later.isoformat(),
        },
    )
    assert o.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "COMPLETE"}).status_code == 200
    s = o.get(f"/api/v1/tenant/jobs/{c.job_id}").json()
    assert Decimal(s["meter_hours"]) == Decimal("8.0") and Decimal(s["nonbillable_hours"]) == Decimal("1.5")
    assert Decimal(s["billable_hours"]) == Decimal("6.5")  # meter hours != billable hours
    assert s["billing_ready"] is True and s["job"]["rate_source"].startswith("RATE_CARD:")


def test_mode_combinations_machine_override_and_violation(api: Api) -> None:
    c = setup_job(api)
    o, now = c.owner, api.clock.now
    _policy(o, {"opening_mode": "MANUAL", "closing_mode": "AUTOMATIC"})
    _policy(o, {"opening_mode": "AUTOMATIC"}, scope="MACHINE", ref=c.t.machine_id)  # per-machine override
    eff = o.get("/api/v1/tenant/policies/METER_CAPTURE/effective", machine_id=c.t.machine_id).json()
    assert (eff["values"]["opening_mode"], eff["values"]["closing_mode"]) == ("AUTOMATIC", "AUTOMATIC")
    wrong = _submit(api, o, capture(c.job_id, "OPENING", "50.0", now, mode="MANUAL", photo_id=photo(api, o)))
    assert "MODE_POLICY_VIOLATION" in _types(wrong) and wrong["capture"]["state"] == "PROVISIONAL"
    tenant_eff = o.get("/api/v1/tenant/policies/METER_CAPTURE/effective").json()["values"]
    assert (tenant_eff["opening_mode"], tenant_eff["closing_mode"]) == ("MANUAL", "AUTOMATIC")


def test_every_reading_attempts_gps_soft_and_hard_enforcement(api: Api) -> None:
    c = setup_job(api)
    o, now = c.owner, api.clock.now
    no_fix = {"status": "PERMISSION_DENIED"}
    r = _submit(api, o, capture(c.job_id, "OPENING", "10.0", now, photo_id=photo(api, o), gps=no_fix))
    assert r["capture"]["state"] == "PROVISIONAL" and "GPS_UNAVAILABLE" in _types(r)
    assert r["capture"]["latitude"] is None  # never fabricated
    bad = o.post(
        "/api/v1/tenant/meter-captures",
        capture(c.job_id, "OPENING", "10.0", now, gps={"status": "NO_FIX", "latitude": -6.8, "longitude": 39.2}),
    )
    assert bad.status_code == 422  # coordinates without a fix are rejected at the contract
    job2 = new_job(
        api, c, "J-002", machine_id=api.add_machines(o, 1, enroll_on=now.date(), prefix="HARD")[0], rate="70000"
    )
    _policy(o, {"gps_enforcement": "HARD"})
    hard = _submit(api, o, capture(job2, "OPENING", "5.0", now, photo_id=photo(api, o), gps={"status": "TIMEOUT"}))
    assert hard["capture"]["state"] == "REJECTED"
    assert (
        o.post(f"/api/v1/tenant/jobs/{job2}/transitions", {"action": "START"}).json()["error"]["code"]
        == "OPENING_REQUIRED"
    )
    inaccurate = _submit(
        api, o, capture(job2, "OPENING", "5.0", now, photo_id=photo(api, o), gps=fix(now, accuracy=400.0))
    )
    assert _types(inaccurate) == {"GPS_INACCURATE"} and inaccurate["capture"]["state"] == "REJECTED"


def test_location_vs_tracker_at_same_time_duplicate_photo_and_idempotency(api: Api) -> None:
    c = setup_job(api)
    o, now = c.owner, api.clock.now
    gw = api.platform.post("/api/v1/platform/telemetry-gateways", {"name": "gw-jobs", "adapter": "TRACCAR"}).json()
    now = now + timedelta(minutes=2)  # tracker was assigned at setup time; report after installation
    api.clock.set_at(now)
    sent = api.client.post(
        "/api/v1/telemetry/traccar",
        json=traccar_payload(c.t.device_id, Fix(now - timedelta(seconds=30), DAR[0], DAR[1], 0, 0)),
        headers={"X-Asseta-Gateway-Key": gw["gateway_key"]},
    )
    assert sent.json()["accepted"] == 1
    pid = photo(api, o)
    far = _submit(
        api, o, capture(c.job_id, "OPENING", "300.0", now, photo_id=pid, gps=fix(now, lat=DAR[0] + 0.02))
    )  # ~2.2 km from the machine's tracker
    assert "LOCATION_MISMATCH" in _types(far)
    comp = far["capture"]["tracker_comparison"]
    assert comp["compared"] and comp["distance_m"] > 2000 and abs(comp["time_offset_s"]) < 300

    replay = o.post(
        "/api/v1/tenant/meter-captures",
        {
            **capture(c.job_id, "OPENING", "300.0", now, photo_id=pid, gps=fix(now, lat=DAR[0] + 0.02)),
            "id": far["capture"]["id"],
        },
    )
    assert replay.status_code == 201 and replay.json()["capture"]["id"] == far["capture"]["id"]
    conflict = o.post(
        "/api/v1/tenant/meter-captures", {**capture(c.job_id, "OPENING", "999.0", now), "id": far["capture"]["id"]}
    )
    assert conflict.json()["error"]["code"] == "CAPTURE_ID_CONFLICT"

    o.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "START"})
    later = now + timedelta(hours=5)
    api.clock.set_at(later)
    reused = _submit(api, o, capture(c.job_id, "CLOSING", "304.0", later, photo_id=pid, gps=fix(later)))
    assert "DUPLICATE_IMAGE" in _types(reused)
    assert "LOCATION_MISMATCH" not in _types(reused)  # no tracker point within the window -> no comparison claim
    assert reused["capture"]["tracker_comparison"]["compared"] is False


def test_meter_decrease_reset_continuity_offline_snapshot_and_immutability(api: Api) -> None:
    c = setup_job(api)
    o, now = c.owner, api.clock.now
    snap = o.get("/api/v1/tenant/policies/METER_CAPTURE/versions").json()
    platform_v1 = [v["id"] for v in snap if v["scope"] == "PLATFORM"]
    _submit(api, o, capture(c.job_id, "OPENING", "500.0", now, photo_id=photo(api, o)))
    o.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "START"})
    t1 = now + timedelta(hours=6)
    api.clock.set_at(t1)
    _submit(api, o, capture(c.job_id, "CLOSING", "505.0", t1, photo_id=photo(api, o), gps=fix(t1)))
    _policy(o, {"opening_mode": "MANUAL"})  # policy changes after the device cached its snapshot
    o.post(
        f"/api/v1/tenant/jobs/{c.job_id}/acknowledgements",
        {
            "client_id": "6f1c2a8e-0000-4000-8000-0000000000aa",
            "method": "NAME_CONFIRMATION",
            "signer_name": "Eng",
            "captured_at": t1.isoformat(),
        },
    )
    o.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "COMPLETE"})
    job2 = new_job(api, c, "J-002")
    t2 = t1 + timedelta(hours=12)
    api.clock.set_at(t2 + timedelta(hours=2))
    offline = _submit(
        api, o, capture(job2, "OPENING", "490.0", t2, photo_id=photo(api, o), gps=fix(t2), snapshot=platform_v1)
    )  # automatic per the device's offline snapshot
    assert "MODE_POLICY_VIOLATION" not in _types(offline) and "|device:" in offline["capture"]["policy_version"]
    assert "METER_DECREASE" in _types(offline)
    gap = _submit(
        api,
        o,
        capture(
            new_job_after_reset(api, c, t2),
            "OPENING",
            "12.0",
            t2 + timedelta(hours=1),
            photo_id=photo(api, o),
            gps=fix(t2 + timedelta(hours=1)),
            snapshot=platform_v1,
        ),
    )
    assert "METER_DECREASE" not in _types(gap)  # approved reset re-bases the comparison

    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        try:
            s.execute(text("UPDATE meter_capture SET reading = 1"))
            raise AssertionError("meter evidence mutated")
        except Exception as exc:
            assert "immutable" in str(exc)


def new_job_after_reset(api: Api, c: Any, at: datetime) -> str:
    """Cancel the decreased-reading job, record an approved meter replacement, open a new job."""
    o = c.owner
    jobs = o.get("/api/v1/tenant/jobs", status="APPROVED").json()["items"]
    o.post(f"/api/v1/tenant/jobs/{jobs[0]['id']}/transitions", {"action": "CANCEL", "reason": "meter replaced"})
    reset = o.post(
        "/api/v1/tenant/meter-resets",
        {
            "machine_id": c.t.machine_id,
            "old_reading": "505.0",
            "new_reading": "10.0",
            "effective_at": (at + timedelta(minutes=30)).isoformat(),
            "reason": "Instrument cluster replaced after fault",
        },
    ).json()
    self_approve = o.post(
        f"/api/v1/tenant/meter-resets/{reset['id']}/decision", {"outcome": "EXPLAINED", "note": "approve own"}
    )
    assert self_approve.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    tid = c.t.tenant["tenant"]["id"]
    approver = Actor(api, "approver-subject", [f"/tenants/{tid}/owner"], tid, email="approver@example.com")
    assert (
        approver.post(
            f"/api/v1/tenant/meter-resets/{reset['id']}/decision",
            {"outcome": "EXPLAINED", "note": "Workshop invoice WS-551"},
        ).json()["status"]
        == "APPROVED"
    )
    return new_job(api, c, "J-003")


def test_supervisor_cannot_approve_and_exception_review_unblocks_billing(api: Api) -> None:
    c = setup_job(api)
    o, now = c.owner, api.clock.now
    tid = c.t.tenant["tenant"]["id"]
    sup = Actor(api, "sup-subject", [f"/tenants/{tid}/supervisor"], tid, email="sup@example.com")
    draft = o.post(
        "/api/v1/tenant/jobs",
        {
            "contract_id": c.contract_id,
            "job_number": "J-X",
            "machine_id": c.t.machine_id,
            "planned_start": now.isoformat(),
        },
    ).json()
    o.post(f"/api/v1/tenant/jobs/{draft['id']}/transitions", {"action": "SUBMIT"})
    assert sup.post(f"/api/v1/tenant/jobs/{draft['id']}/transitions", {"action": "APPROVE"}).status_code == 403
    r = _submit(
        api, sup, capture(c.job_id, "OPENING", "70.0", now, photo_id=photo(api, sup), confidence=0.4, ocr="78.0")
    )
    assert _types(r) == {"LOW_OCR_CONFIDENCE", "MANUAL_CORRECTION"}
    exc = o.get("/api/v1/tenant/exceptions", job_id=c.job_id).json()["items"]
    assert (
        sup.post(
            f"/api/v1/tenant/exceptions/{exc[0]['id']}/review", {"outcome": "EXPLAINED", "note": "glare"}
        ).status_code
        == 403
    )
    for e in exc:
        rv = o.post(
            f"/api/v1/tenant/exceptions/{e['id']}/review",
            {"outcome": "EXPLAINED", "note": "Glare on display; photo verified by owner"},
        )
        assert rv.json()["status"] == "EXPLAINED"
    assert o.get(f"/api/v1/tenant/jobs/{c.job_id}").json()["blocking_exceptions"] == 0
