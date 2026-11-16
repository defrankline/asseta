"""Meter readings (Gate 3 acceptance, prompt.md §10 #5 and R1-E, on DAILY readings after ADR-008): capture-mode
policy, photo/OCR, GPS, tracker location, duplicate photos, idempotency, sequence checks and resets, offline policy
snapshots, immutability and exception review."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.tools.gps_simulator import Fix, traccar_payload
from tests.support.api import Actor, Api
from tests.support.finance import setup_finance
from tests.support.meter import capture, fix, photo, setup_machine
from tests.support.telemetry import DAR

T = "/api/v1/tenant"


def _submit(api: Api, actor: Actor, body: dict[str, Any]) -> dict[str, Any]:
    r = actor.post(f"{T}/meter-captures", body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def _types(result: dict[str, Any]) -> set[str]:
    return {f["type"] for f in result["findings"]}


def _policy(actor: Actor, values: dict[str, Any], scope: str = "TENANT", ref: str | None = None) -> None:
    r = actor.post(
        f"{T}/policies/METER_CAPTURE/versions",
        {"scope": scope, "scope_ref_id": ref, "values": values, "reason": "Owner capture rules"},
    )
    assert r.status_code == 201, r.text


def test_daily_reading_accepted_and_contract_rules(api: Api) -> None:
    c = setup_machine(api)
    o, m, now = c.owner, c.t.machine_id, api.clock.now
    _policy(o, {"manual_photo_required": False})
    first = _submit(api, o, capture(m, "1200.0", now, photo_id=photo(api, o)))
    assert first["capture"]["state"] == "ACCEPTED" and first["findings"] == []
    assert first["capture"]["kind"] == "DAILY" and first["capture"]["machine_id"] == m
    assert first["capture"]["policy_version"].startswith("METER_CAPTURE@P1.T1")

    later = now + timedelta(hours=9)
    api.clock.set_at(later)
    manual = _submit(api, o, capture(m, "1208.0", later, mode="MANUAL"))
    assert _types(manual) == {"MODE_POLICY_VIOLATION"} and manual["capture"]["state"] == "PROVISIONAL"
    listed = o.get(f"{T}/meter-captures", machine_id=m, kind="DAILY").json()["items"]
    assert [Decimal(x["reading"]) for x in listed] == [1208, 1200]  # latest captured first

    # Only DAILY readings exist; the machine is required.
    opening_kind = o.post(f"{T}/meter-captures", {**capture(m, "1209.0", later), "kind": "OPENING"})
    assert opening_kind.status_code == 422
    no_machine = o.post(f"{T}/meter-captures", {**capture(m, "1209.0", later), "machine_id": None})
    assert (no_machine.status_code, no_machine.json()["error"]["code"]) == (422, "VALIDATION_FAILED")
    # The retired opening/closing modes: one capture_mode; the old names are refused in new versions.
    eff = o.get(f"{T}/policies/METER_CAPTURE/effective").json()["values"]
    assert eff["capture_mode"] == "AUTOMATIC" and not {"opening_mode", "closing_mode"} & set(eff)
    r = o.post(
        f"{T}/policies/METER_CAPTURE/versions",
        {"scope": "TENANT", "values": {"closing_mode": "MANUAL"}, "reason": "Old setting"},
    )
    assert (r.status_code, r.json()["error"]["code"]) == (422, "POLICY_UNKNOWN_FIELD")


def test_mode_machine_override_and_violation(api: Api) -> None:
    c = setup_machine(api)
    o, m, now = c.owner, c.t.machine_id, api.clock.now
    _policy(o, {"capture_mode": "MANUAL"})
    _policy(o, {"capture_mode": "AUTOMATIC"}, scope="MACHINE", ref=m)  # per-machine override
    eff = o.get(f"{T}/policies/METER_CAPTURE/effective", machine_id=m).json()
    assert eff["values"]["capture_mode"] == "AUTOMATIC"
    wrong = _submit(api, o, capture(m, "50.0", now, mode="MANUAL", photo_id=photo(api, o)))
    assert "MODE_POLICY_VIOLATION" in _types(wrong) and wrong["capture"]["state"] == "PROVISIONAL"
    assert o.get(f"{T}/policies/METER_CAPTURE/effective").json()["values"]["capture_mode"] == "MANUAL"
    [other] = api.add_machines(o, 1, enroll_on=now.date(), prefix="MAN")
    fine = _submit(api, o, capture(other, "70.0", now, mode="MANUAL", photo_id=photo(api, o)))
    assert fine["findings"] == [] and fine["capture"]["state"] == "ACCEPTED"


def test_every_reading_attempts_gps_soft_and_hard_enforcement(api: Api) -> None:
    c = setup_machine(api)
    o, m, now = c.owner, c.t.machine_id, api.clock.now
    no_fix = {"status": "PERMISSION_DENIED"}
    r = _submit(api, o, capture(m, "10.0", now, photo_id=photo(api, o), gps=no_fix))
    assert r["capture"]["state"] == "PROVISIONAL" and "GPS_UNAVAILABLE" in _types(r)
    assert r["capture"]["latitude"] is None  # never fabricated
    bad = o.post(
        f"{T}/meter-captures",
        capture(m, "10.0", now, gps={"status": "NO_FIX", "latitude": -6.8, "longitude": 39.2}),
    )
    assert bad.status_code == 422  # coordinates without a fix are rejected at the contract
    [m2] = api.add_machines(o, 1, enroll_on=now.date(), prefix="HARD")
    _policy(o, {"gps_enforcement": "HARD"})
    hard = _submit(api, o, capture(m2, "5.0", now, photo_id=photo(api, o), gps={"status": "TIMEOUT"}))
    assert hard["capture"]["state"] == "REJECTED"
    inaccurate = _submit(api, o, capture(m2, "5.0", now, photo_id=photo(api, o), gps=fix(now, accuracy=400.0)))
    assert _types(inaccurate) == {"GPS_INACCURATE"} and inaccurate["capture"]["state"] == "REJECTED"


def test_location_vs_tracker_at_same_time_duplicate_photo_and_idempotency(api: Api) -> None:
    c = setup_machine(api)
    o, m, now = c.owner, c.t.machine_id, api.clock.now
    gw = api.platform.post("/api/v1/platform/telemetry-gateways", {"name": "gw-meter", "adapter": "TRACCAR"}).json()
    now = now + timedelta(minutes=2)  # tracker was assigned at setup time; report after installation
    api.clock.set_at(now)
    sent = api.client.post(
        "/api/v1/telemetry/traccar",
        json=traccar_payload(c.t.device_id, Fix(now - timedelta(seconds=30), DAR[0], DAR[1], 0, 0)),
        headers={"X-Asseta-Gateway-Key": gw["gateway_key"]},
    )
    assert sent.json()["accepted"] == 1
    pid = photo(api, o)
    far = _submit(api, o, capture(m, "300.0", now, photo_id=pid, gps=fix(now, lat=DAR[0] + 0.02)))
    assert "LOCATION_MISMATCH" in _types(far)  # ~2.2 km from the machine's tracker
    comp = far["capture"]["tracker_comparison"]
    assert comp["compared"] and comp["distance_m"] > 2000 and abs(comp["time_offset_s"]) < 300

    replay = o.post(
        f"{T}/meter-captures",
        {**capture(m, "300.0", now, photo_id=pid, gps=fix(now, lat=DAR[0] + 0.02)), "id": far["capture"]["id"]},
    )
    assert replay.status_code == 201 and replay.json()["capture"]["id"] == far["capture"]["id"]
    conflict = o.post(f"{T}/meter-captures", {**capture(m, "999.0", now), "id": far["capture"]["id"]})
    assert conflict.json()["error"]["code"] == "CAPTURE_ID_CONFLICT"

    later = now + timedelta(hours=5)
    api.clock.set_at(later)
    reused = _submit(api, o, capture(m, "304.0", later, photo_id=pid, gps=fix(later)))
    assert "DUPLICATE_IMAGE" in _types(reused)
    assert "LOCATION_MISMATCH" not in _types(reused)  # no tracker point within the window -> no comparison claim
    assert reused["capture"]["tracker_comparison"]["compared"] is False


def test_meter_decrease_reset_offline_snapshot_and_immutability(api: Api) -> None:
    c = setup_machine(api)
    o, m, now = c.owner, c.t.machine_id, api.clock.now
    snap = o.get(f"{T}/policies/METER_CAPTURE/versions").json()
    platform_v1 = [v["id"] for v in snap if v["scope"] == "PLATFORM"]
    _submit(api, o, capture(m, "500.0", now, photo_id=photo(api, o)))
    t1 = now + timedelta(hours=6)
    api.clock.set_at(t1)
    ok = _submit(api, o, capture(m, "505.0", t1, photo_id=photo(api, o), gps=fix(t1)))
    assert ok["findings"] == []
    api.clock.set_at(t1 + timedelta(hours=1))
    jump = _submit(api, o, capture(m, "520.0", t1 + timedelta(hours=1), photo_id=photo(api, o)))
    assert _types(jump) == {"IMPOSSIBLE_INCREMENT"}  # 15 hours in one hour
    _policy(o, {"capture_mode": "MANUAL"})  # policy changes after the device cached its snapshot
    t2 = t1 + timedelta(hours=12)
    api.clock.set_at(t2 + timedelta(hours=2))
    offline = _submit(api, o, capture(m, "490.0", t2, photo_id=photo(api, o), gps=fix(t2), snapshot=platform_v1))
    assert "MODE_POLICY_VIOLATION" not in _types(offline) and "|device:" in offline["capture"]["policy_version"]
    assert "METER_DECREASE" in _types(offline)

    # An approved meter replacement re-bases the comparison (never by the person who asked for it).
    reset = o.post(
        f"{T}/meter-resets",
        {
            "machine_id": m,
            "old_reading": "505.0",
            "new_reading": "10.0",
            "effective_at": (t2 + timedelta(minutes=30)).isoformat(),
            "reason": "Instrument cluster replaced after fault",
        },
    ).json()
    self_approve = o.post(f"{T}/meter-resets/{reset['id']}/decision", {"outcome": "EXPLAINED", "note": "approve own"})
    assert self_approve.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    tid = c.t.tenant["tenant"]["id"]
    approver = Actor(api, "approver-subject", [f"/tenants/{tid}/owner"], tid, email="approver@example.com")
    decided = approver.post(
        f"{T}/meter-resets/{reset['id']}/decision", {"outcome": "EXPLAINED", "note": "Workshop invoice WS-551"}
    )
    assert decided.json()["status"] == "APPROVED"
    t3 = t2 + timedelta(hours=1)
    after = _submit(api, o, capture(m, "12.0", t3, photo_id=photo(api, o), gps=fix(t3), snapshot=platform_v1))
    assert "METER_DECREASE" not in _types(after)

    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        try:
            s.execute(text("UPDATE meter_capture SET reading = 1"))
            raise AssertionError("meter evidence mutated")
        except Exception as exc:
            assert "immutable" in str(exc)


def test_supervisor_reads_own_machines_and_cannot_review_exceptions(api: Api) -> None:
    f = setup_finance(api)  # the supervisor is assigned to the machine
    o, sup, m, now = f.owner, f.supervisor, f.c.t.machine_id, api.clock.now
    _policy(o, {"capture_mode": "AUTOMATIC"})
    [other] = api.add_machines(o, 1, enroll_on=now.date(), prefix="OTH")
    elsewhere = sup.post(f"{T}/meter-captures", capture(other, "70.0", now, photo_id=photo(api, sup)))
    assert (elsewhere.status_code, elsewhere.json()["error"]["code"]) == (404, "MACHINE_NOT_FOUND")
    r = _submit(api, sup, capture(m, "70.0", now, photo_id=photo(api, sup), confidence=0.4, ocr="78.0"))
    assert _types(r) == {"LOW_OCR_CONFIDENCE", "MANUAL_CORRECTION"}
    exc = o.get(f"{T}/exceptions", meter_capture_id=r["capture"]["id"]).json()["items"]
    assert {e["exception_type"] for e in exc} == {"LOW_OCR_CONFIDENCE", "MANUAL_CORRECTION"}
    review = {"outcome": "EXPLAINED", "note": "glare"}
    assert sup.post(f"{T}/exceptions/{exc[0]['id']}/review", review).status_code == 403
    for e in exc:
        rv = o.post(
            f"{T}/exceptions/{e['id']}/review",
            {"outcome": "EXPLAINED", "note": "Glare on display; photo verified by owner"},
        )
        assert rv.json()["status"] == "EXPLAINED"
    assert o.get(f"{T}/exceptions", meter_capture_id=r["capture"]["id"], status="OPEN").json()["items"] == []


def test_review_lists_photo_link_and_tracker_coordinates(api: Api) -> None:
    c = setup_machine(api)
    o, now = c.owner, api.clock.now + timedelta(minutes=2)
    api.clock.set_at(now)
    gw = api.platform.post("/api/v1/platform/telemetry-gateways", {"name": "gw-review", "adapter": "TRACCAR"}).json()
    api.client.post(
        "/api/v1/telemetry/traccar",
        json=traccar_payload(c.t.device_id, Fix(now - timedelta(seconds=20), DAR[0], DAR[1], 0, 0)),
        headers={"X-Asseta-Gateway-Key": gw["gateway_key"]},
    )
    pid = photo(api, o)
    r = _submit(api, o, capture(c.t.machine_id, "42.0", now, photo_id=pid))
    assert r["capture"]["photo_attachment_id"] == pid
    comp = r["capture"]["tracker_comparison"]
    assert comp["tracker_latitude"] == DAR[0] and comp["tracker_longitude"] == DAR[1]
    url = o.get(f"{T}/attachments/{pid}/url").json()
    assert url["expires_in_seconds"] == 300
    cards = o.get(f"{T}/rate-cards", machine_category_id=c.category_id).json()
    assert len(cards) == 1 and cards[0]["hourly_rate"] == "85000.0000"
    reset = o.post(
        f"{T}/meter-resets",
        {
            "machine_id": c.t.machine_id,
            "old_reading": "42.0",
            "new_reading": "0.0",
            "effective_at": now.isoformat(),
            "reason": "Cluster replaced under warranty",
        },
    ).json()
    pending = o.get(f"{T}/meter-resets", status="PENDING").json()
    assert [p["id"] for p in pending] == [reset["id"]] and pending[0]["requested_by"]
