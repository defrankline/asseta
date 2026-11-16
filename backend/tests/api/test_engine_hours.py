"""Engine-hour accountability (design B, controls [3.2.1]-[3.2.9]): approved baselines, DAILY readings (online and
offline), the machine ledger and its reconciliation (hours inside machine reports are REPORTED), classifications by
a second person, flags, ageing into an investigation (never a verdict) and two-person reading corrections. Every
control is a tenant policy switch; the platform defaults are on."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.notification.reminders import run_reminders
from asseta.tools.gps_simulator import Fix
from tests.support.api import Actor, Api
from tests.support.finance import role
from tests.support.intelligence import cases, signals, sweep
from tests.support.machine_reports import idle, report_body, setup_reports, submit
from tests.support.meter import MachineCtx, capture, engine_hours_policy, setup_machine
from tests.support.notify import sql, sync_mirror
from tests.support.telemetry import DAR, Telemetry

T = "/api/v1/tenant"
ON: dict[str, Any] = {"daily_report_required": True}


class _Gateway(Telemetry):
    """Another tracker gateway of the platform (the test's tracker model already exists)."""

    def __init__(self, api: Api) -> None:
        self.api = api
        g = api.platform.post(
            "/api/v1/platform/telemetry-gateways", {"name": f"gw-{uuid.uuid4().hex[:8]}", "adapter": "TRACCAR"}
        )
        assert g.status_code == 201, g.text
        self.key = g.json()["gateway_key"]


def _ctx(api: Api, name: str = "Engine Co", device: str = "ENG-1") -> tuple[MachineCtx, Actor, str]:
    c = setup_machine(api, name, device)
    engine_hours_policy(c.owner, **ON)  # back to the platform defaults (the machine helper switches it off)
    tid = c.t.tenant["tenant"]["id"]
    return c, role(api, tid, "owner", f"approver-{device}"), tid


def _ok(r: Any, status: int = 200) -> dict[str, Any]:
    assert r.status_code == status, r.text
    out: dict[str, Any] = r.json()
    return out


def _code(r: Any) -> str:
    return str(r.json()["error"]["code"])


def _daily(machine_id: str, reading: str, at: datetime) -> dict[str, Any]:
    return capture(machine_id, reading, at, mode="MANUAL")


def _cap(actor: Actor, body: dict[str, Any]) -> Any:
    """Submit a reading at its capture time (the server clock follows, so no clock-skew finding)."""
    at = datetime.fromisoformat(body["captured_at"])
    if at > actor.api.clock.now:
        actor.api.clock.set_at(at)
    return actor.post(f"{T}/meter-captures", body)


def _baseline(api: Api, c: MachineCtx, approver: Actor, reading: str, at: datetime) -> dict[str, Any]:
    proposed = _ok(
        c.owner.post(
            f"{T}/meter-baselines",
            {"machine_id": c.t.machine_id, "reading": reading, "captured_at": at.isoformat(), "note": "Initial"},
        ),
        201,
    )
    return _ok(
        approver.post(
            f"{T}/meter-baselines/{proposed['id']}/decision", {"decision": "APPROVE", "note": "Evidence checked"}
        )
    )


def _manual_policy(owner: Actor) -> None:
    r = owner.post(
        f"{T}/policies/METER_CAPTURE/versions",
        {
            "scope": "TENANT",
            "values": {"capture_mode": "MANUAL", "manual_photo_required": False},
            "reason": "Manual capture for engine-hour tests",
        },
    )
    assert r.status_code == 201, r.text


def test_a_baseline_needs_a_second_person(api: Api) -> None:
    c, approver, tid = _ctx(api)
    o, t0 = c.owner, api.clock.now
    _manual_policy(o)
    status = _ok(o.get(f"{T}/engine-hours/machines/{c.t.machine_id}"))
    assert status["status"] == "NO_BASELINE" and status["baseline"] is None

    operator = role(api, tid, "operator", "eng-operator")  # operators get no new permissions
    body = {"machine_id": c.t.machine_id, "reading": "999.5", "captured_at": (t0 - timedelta(hours=1)).isoformat()}
    assert operator.post(f"{T}/meter-baselines", body).status_code == 403
    proposed = _ok(o.post(f"{T}/meter-baselines", body), 201)
    assert proposed["status"] == "PROPOSED" and proposed["source"] == "CAPTURE"
    assert _code(o.post(f"{T}/meter-baselines", body)) == "BASELINE_PENDING"
    decision = {"decision": "APPROVE", "note": "Photo matches"}
    assert _code(o.post(f"{T}/meter-baselines/{proposed['id']}/decision", decision)) == "SEGREGATION_OF_DUTIES"
    approved = _ok(approver.post(f"{T}/meter-baselines/{proposed['id']}/decision", decision))
    assert approved["status"] == "APPROVED" and approved["decided_by"] is not None
    assert _code(o.post(f"{T}/meter-baselines", body)) == "BASELINE_EXISTS"  # re-baseline only via meter reset
    page = _ok(o.get(f"{T}/meter-baselines", q=c.t.device_id.replace("-", "")))
    assert page["total"] == 1 and page["items"][0]["machine_code"].startswith("ENG1")
    assert _ok(o.get(f"{T}/meter-baselines", q="no-such-machine"))["total"] == 0


def test_existing_machine_baseline_from_its_earliest_reading(api: Api) -> None:
    c, approver, tid = _ctx(api)
    o, t0 = c.owner, api.clock.now
    _manual_policy(o)
    first = _ok(_cap(o, _daily(c.t.machine_id, "500.0", t0)), 201)
    proposed = _ok(o.post(f"{T}/meter-baselines/from-reading", {"machine_id": c.t.machine_id}), 201)
    assert proposed["source"] == "READING" and proposed["source_capture_id"] == first["capture"]["id"]
    assert Decimal(proposed["reading"]) == Decimal("500.0")
    # the approver may not be the person who proposed it nor the one who recorded the reading
    other = role(api, tid, "owner", "second-owner")
    decided = _ok(
        other.post(f"{T}/meter-baselines/{proposed['id']}/decision", {"decision": "REJECT", "note": "Blurry"})
    )
    assert decided["status"] == "REJECTED"
    again = _ok(o.post(f"{T}/meter-baselines/from-reading", {"machine_id": c.t.machine_id}), 201)
    _ok(approver.post(f"{T}/meter-baselines/{again['id']}/decision", {"decision": "APPROVE", "note": "Checked"}))
    ledger = _ok(o.get(f"{T}/engine-hours/machines/{c.t.machine_id}"))
    assert ledger["intervals"] == [] and ledger["status"] == "RECONCILED"  # the reading *is* the baseline point


def test_daily_readings_ledger_flags_and_tenant_wide_list(api: Api) -> None:
    ctx = setup_reports(api, "Engine Co", "ENG-1")  # baseline 1000, approved, two hours ago
    f, m = ctx.f, ctx.machine_id
    o, t0 = f.owner, api.clock.now
    engine_hours_policy(o, **ON)
    daily = _ok(_cap(o, _daily(m, "1001", t0 + timedelta(hours=1))), 201)  # 3 h after the baseline
    assert daily["capture"]["machine_id"] == m and daily["capture"]["kind"] == "DAILY"
    assert daily["capture"]["state"] == "ACCEPTED"
    # A submitted machine report accounts for every hour from the baseline to its reading.
    api.clock.set_at(t0 + timedelta(hours=3))
    rep = submit(f.supervisor, report_body(m, "1003", api.clock.now, [idle(ctx.reasons["BREAKDOWN"], 3)]))
    _ok(_cap(o, _daily(m, "1003.5", t0 + timedelta(hours=4))), 201)
    _ok(_cap(o, _daily(m, "1005", t0 + timedelta(hours=6))), 201)  # many DAILY readings are fine

    rec = _ok(o.get(f"{T}/engine-hours/machines/{m}"))
    seg = [
        (i["segments"][0]["kind"], Decimal(i["hours"]), i["segments"][0]["classification"]) for i in rec["intervals"]
    ]
    assert seg == [
        ("REPORTED", Decimal("1"), "NOT_APPLICABLE"),
        ("REPORTED", Decimal("2"), "NOT_APPLICABLE"),
        ("UNALLOCATED", Decimal("0.5"), "UNEXPLAINED"),
        ("UNALLOCATED", Decimal("1.5"), "UNEXPLAINED"),
    ]
    reported = rec["intervals"][0]["segments"][0]
    assert (reported["report_id"], reported["report_number"]) == (rep["id"], rep["report_number"])
    totals = rec["totals"]
    assert Decimal(totals["total_hours"]) == Decimal("5") and Decimal(totals["unexplained_hours"]) == Decimal("2")
    assert Decimal(totals["reported_hours"]) == Decimal("3")
    assert rec["status"] == "UNEXPLAINED" and rec["intervals"][0]["start"]["source"] == "BASELINE"

    # Flags: the hours inside the report were flagged as their readings came in; they stay open while it waits.
    flags = _ok(o.get(f"{T}/exceptions", exception_type="UNEXPLAINED_HOURS"))
    assert flags["total"] == 4 and all(f["meter_capture_id"] is None for f in flags["items"])
    # Its approval explains them (the approver's decision); the hours after the report stay open.
    _ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))
    flags = _ok(o.get(f"{T}/exceptions", exception_type="UNEXPLAINED_HOURS"))
    by_status = {(x["status"], x["evidence"]["hours"]) for x in flags["items"]}
    assert by_status == {("EXPLAINED", "1.00"), ("EXPLAINED", "2.00"), ("OPEN", "0.50"), ("OPEN", "1.50")}
    _cap(o, _daily(m, "1005.2", t0 + timedelta(hours=8)))
    assert _ok(o.get(f"{T}/exceptions", exception_type="UNEXPLAINED_HOURS"))["total"] == 5  # once per segment

    items = _ok(o.get(f"{T}/engine-hours/unallocated"))
    assert items["total"] == 3
    assert [Decimal(i["hours"]) for i in items["items"]] == [Decimal("0.5"), Decimal("1.5"), Decimal("0.2")]
    assert _ok(o.get(f"{T}/engine-hours/unallocated", q="ENG1"))["total"] == 3
    assert _ok(o.get(f"{T}/engine-hours/unallocated", q="nothing-like-it"))["total"] == 0
    summary = _ok(o.get(f"{T}/engine-hours/machines", q="ENG1"))
    assert summary["total"] == 1 and summary["items"][0]["open_items"] == 3
    assert _ok(o.get(f"{T}/engine-hours/machines", status="RECONCILED"))["total"] == 0


def test_classification_needs_a_second_person_and_tenant_lists(api: Api) -> None:
    c, approver, tid = _ctx(api)
    o, t0 = c.owner, api.clock.now
    _manual_policy(o)
    _baseline(api, c, approver, "200", t0 - timedelta(hours=1))
    _ok(_cap(o, _daily(c.t.machine_id, "204", t0 + timedelta(hours=4))), 201)
    seg = _ok(o.get(f"{T}/engine-hours/unallocated"))["items"][0]

    maint = _ok(
        o.post(f"{T}/engine-hour-reasons", {"kind": "NON_CUSTOMER_CATEGORY", "code": "MAINT", "name": "Maintenance"}),
        201,
    )
    fault = _ok(
        o.post(f"{T}/engine-hour-reasons", {"kind": "VARIANCE_REASON", "code": "FAULT", "name": "Meter fault"}), 201
    )
    assert _code(o.post(f"{T}/engine-hour-reasons", {"kind": "VARIANCE_REASON", "code": "FAULT", "name": "x"})) == (
        "DUPLICATE_REASON"
    )
    assert _ok(o.get(f"{T}/engine-hour-reasons", kind="VARIANCE_REASON"))["total"] == 1
    assert _ok(o.get(f"{T}/engine-hour-reasons", q="maint"))["total"] == 1
    renamed = _ok(o.put(f"{T}/engine-hour-reasons/{maint['id']}", {"code": "MAINT", "name": "Servicing", "version": 1}))
    assert renamed["name"] == "Servicing" and renamed["version"] == 2

    body = {
        "machine_id": c.t.machine_id,
        "start_ref": seg["start"]["ref"],
        "end_ref": seg["end"]["ref"],
        "outcome": "APPROVED_NON_CUSTOMER",
        "reason_id": fault["id"],
        "note": "Moved to the yard for a service",
    }
    assert _code(o.post(f"{T}/engine-hours/classifications", body)) == "REASON_NOT_ALLOWED"
    body["reason_id"] = maint["id"]
    # DEC-032 Phase 3: a tenant can require evidence on classifications.
    engine_hours_policy(o, **ON, classification_evidence_required=True)
    assert _code(o.post(f"{T}/engine-hours/classifications", body)) == "EVIDENCE_REQUIRED"
    engine_hours_policy(o, **ON)
    proposed = _ok(o.post(f"{T}/engine-hours/classifications", body), 201)
    assert proposed["status"] == "PROPOSED" and Decimal(proposed["hours"]) == Decimal("4")
    assert _code(o.post(f"{T}/engine-hours/classifications", body)) == "CLASSIFICATION_PENDING"
    pending = _ok(o.get(f"{T}/engine-hours/unallocated"))["items"][0]
    assert pending["classification"] == "UNEXPLAINED" and pending["proposal"]["id"] == proposed["id"]
    decide = {"decision": "APPROVE", "note": "Service record seen"}
    url = f"{T}/engine-hours/classifications/{proposed['id']}/decision"
    assert _code(o.post(url, decide)) == "SEGREGATION_OF_DUTIES"
    field = role(api, tid, "supervisor", "eng-field")  # field roles never decide a classification
    assert field.post(url, decide).status_code == 403
    done = _ok(approver.post(url, decide))
    assert done["status"] == "APPROVED" and done["reason_name"] == "Servicing"
    rec = _ok(o.get(f"{T}/engine-hours/machines/{c.t.machine_id}"))
    assert rec["intervals"][0]["segments"][0]["classification"] == "APPROVED_NON_CUSTOMER"
    assert rec["status"] == "RECONCILED" and Decimal(rec["totals"]["approved_non_customer_hours"]) == Decimal("4")
    flag = _ok(o.get(f"{T}/exceptions", exception_type="UNEXPLAINED_HOURS"))["items"][0]
    assert flag["status"] == "EXPLAINED"
    assert _ok(o.get(f"{T}/engine-hours/unallocated"))["total"] == 0
    assert _ok(o.get(f"{T}/engine-hours/unallocated", classification="APPROVED_NON_CUSTOMER"))["total"] == 1
    assert _ok(o.get(f"{T}/engine-hours/classifications", q="yard"))["total"] == 1

    # deactivated list entries are refused for new explanations; no approval needed when the tenant says so
    _ok(o.post(f"{T}/engine-hour-reasons/{fault['id']}/deactivate", {"reason": "Not used any more"}))
    _ok(_cap(o, _daily(c.t.machine_id, "206", t0 + timedelta(hours=8))), 201)
    seg2 = _ok(o.get(f"{T}/engine-hours/unallocated"))["items"][0]
    body2 = {**body, "start_ref": seg2["start"]["ref"], "end_ref": seg2["end"]["ref"], "outcome": "IDENTIFIED_VARIANCE"}
    assert _code(o.post(f"{T}/engine-hours/classifications", {**body2, "reason_id": fault["id"]})) == (
        "REASON_NOT_ALLOWED"
    )
    _ok(o.post(f"{T}/engine-hour-reasons/{fault['id']}/reactivate", {"reason": "Needed again"}))
    engine_hours_policy(o, classification_requires_approval=False)
    direct = _ok(o.post(f"{T}/engine-hours/classifications", {**body2, "reason_id": fault["id"]}), 201)
    assert direct["status"] == "APPROVED"


def test_unexplained_hours_age_into_an_investigation_never_a_verdict(api: Api) -> None:
    c, approver, tid = _ctx(api)
    o, t0 = c.owner, api.clock.now
    _manual_policy(o)
    _baseline(api, c, approver, "50", t0 - timedelta(hours=1))
    _ok(_cap(o, _daily(c.t.machine_id, "55", t0 + timedelta(hours=5))), 201)
    sweep(api, tid)
    assert [x for x in cases(o) if "Engine hours" in x["title"]] == []  # not old enough
    api.clock.set_at(t0 + timedelta(days=3, hours=6))
    sweep(api, tid)
    sweep(api, tid)  # idempotent
    opened = [x for x in cases(o) if "Engine hours" in x["title"]]
    assert len(opened) == 1 and opened[0]["status"] == "OPEN"
    assert "fraud" not in opened[0]["title"].lower()
    item = _ok(o.get(f"{T}/engine-hours/unallocated"))["items"][0]
    assert item["classification"] == "UNEXPLAINED" and item["investigation_due"] is True  # time never reclassifies

    # switched off by the tenant: newer unexplained hours never open (or feed) a case, however old
    engine_hours_policy(o, unexplained_investigation_after_days=None)
    _ok(_cap(o, _daily(c.t.machine_id, "57", api.clock.now)), 201)
    api.clock.set_at(api.clock.now + timedelta(days=10))
    sweep(api, tid)
    aged = [x for x in signals(o) if x["rule_code"] == "UNEXPLAINED_ENGINE_HOURS"]
    assert len(aged) == 1  # only the segment that aged while the switch was on
    assert len(_ok(o.get(f"{T}/engine-hours/unallocated"))["items"]) == 2  # both still visible, unexplained


def test_corrections_need_a_reason_and_a_second_person(api: Api) -> None:
    c, approver, _ = _ctx(api)
    o, t0 = c.owner, api.clock.now
    _manual_policy(o)
    _baseline(api, c, approver, "300", t0 - timedelta(hours=1))
    wrong = _ok(_cap(o, _daily(c.t.machine_id, "330", t0 + timedelta(hours=2))), 201)
    replacement = _daily(c.t.machine_id, "303", t0 + timedelta(hours=2))
    inline = {**replacement, "supersedes_id": wrong["capture"]["id"]}
    assert _code(_cap(o, inline)) == "CORRECTION_APPROVAL_REQUIRED"
    body = {"superseded_capture_id": wrong["capture"]["id"], "reason": "short", "replacement": replacement}
    assert o.post(f"{T}/meter-corrections", body).status_code == 422  # reason needs >= 10 characters
    body["reason"] = "Typed 330 instead of 303 on the meter"
    proposed = _ok(o.post(f"{T}/meter-corrections", body), 201)
    assert proposed["status"] == "PROPOSED" and Decimal(proposed["old_reading"]) == Decimal("330")
    assert _ok(o.post(f"{T}/meter-corrections", body), 201)["id"] == proposed["id"]  # idempotent replay
    url = f"{T}/meter-corrections/{proposed['id']}/decision"
    assert _code(o.post(url, {"decision": "APPROVE", "note": "Looks right"})) == "SEGREGATION_OF_DUTIES"
    done = _ok(approver.post(url, {"decision": "APPROVE", "note": "Photo shows 303"}))
    assert done["status"] == "APPROVED"
    caps = {x["id"]: x for x in _ok(o.get(f"{T}/meter-captures", machine_id=c.t.machine_id))["items"]}
    assert caps[wrong["capture"]["id"]]["state"] == "SUPERSEDED"
    new = caps[replacement["id"]]
    assert new["supersedes_id"] == wrong["capture"]["id"] and Decimal(new["reading"]) == Decimal("303")
    audit = sql(
        "SELECT action, before, after FROM audit_event WHERE entity_type = 'meter_correction' ORDER BY occurred_at"
    )
    approved = [a for a in audit if a.action == "meter.correction.approved"]
    assert approved and approved[0].after["superseded_capture_id"] == wrong["capture"]["id"]
    assert approved[0].before["reading"] == "330.00"
    rec = _ok(o.get(f"{T}/engine-hours/machines/{c.t.machine_id}"))
    assert Decimal(rec["totals"]["total_hours"]) == Decimal("3")

    # policy off: an approver's correction applies directly (the behaviour before two-person corrections)
    engine_hours_policy(o, correction_requires_second_person=False)
    again = _daily(c.t.machine_id, "303.5", t0 + timedelta(hours=2))
    _ok(_cap(o, {**again, "supersedes_id": replacement["id"]}), 201)


def _engine_on(api: Api, c: MachineCtx, at: datetime) -> None:
    """The machine's tracker reports the engine running for 20 minutes from `at` (a working machine that day)."""
    tel = _Gateway(api)
    for minutes, ignition in ((0, True), (20, False)):
        when = at + timedelta(minutes=minutes)
        api.clock.set_at(when + timedelta(seconds=2))
        assert tel.send(c.t.device_id, Fix(when, DAR[0], DAR[1], 0.0, 0.0, ignition=ignition))["accepted"] == 1
    tel.drain_timeline()


def test_missing_daily_report_flag_and_reminder(api: Api) -> None:
    c, approver, tid = _ctx(api)
    o, t0 = c.owner, api.clock.now  # 2026-11-01 09:00 UTC = 12:00 in Dar es Salaam
    _manual_policy(o)
    _baseline(api, c, approver, "10", t0 - timedelta(hours=1))
    _engine_on(api, c, t0)
    _ok(_cap(o, _daily(c.t.machine_id, "10", api.clock.now)), 201)
    sweep(api, tid)
    assert _ok(o.get(f"{T}/exceptions", exception_type="MISSING_DAILY_REPORT"))["total"] == 0  # reported today
    day2 = datetime.combine(date(2026, 11, 2), datetime.min.time(), t0.tzinfo)
    _engine_on(api, c, day2 + timedelta(hours=6))  # 09:00 local on 2 Nov: the machine worked
    api.clock.set_at(day2 + timedelta(hours=16))
    sweep(api, tid)  # 19:00 local on 2 Nov, cut-off 18:00, no reading that day
    flags = _ok(o.get(f"{T}/exceptions", exception_type="MISSING_DAILY_REPORT"))["items"]
    assert len(flags) == 1 and flags[0]["evidence"]["day"] == "2026-11-02"
    assert flags[0]["machine_id"] == c.t.machine_id and flags[0]["evidence"]["basis"] == "ENGINE_ACTIVITY"
    sync_mirror(api)  # the owner as a Keycloak member: reachable by permission-addressed reminders
    run_reminders(get_sessionmaker(), api.clock.now)
    rows = sql(
        "SELECT count(*) AS n FROM notification WHERE tenant_id = :t AND notification_type = 'MISSING_DAILY_REPORT'",
        t=tid,
    )
    assert rows[0].n >= 1
    engine_hours_policy(o, scope="MACHINE", ref=c.t.machine_id, daily_report_required=False)
    api.clock.set_at(api.clock.now + timedelta(days=1))
    sweep(api, tid)
    assert _ok(o.get(f"{T}/exceptions", exception_type="MISSING_DAILY_REPORT"))["total"] == 1  # machine exempted


def test_daily_reading_and_proposals_from_an_offline_device(api: Api) -> None:
    c, approver, tid = _ctx(api)
    o, t0 = c.owner, api.clock.now
    _manual_policy(o)
    sup = role(api, tid, "supervisor", "eng-sup")
    staff = _ok(
        o.post(f"{T}/staff", {"full_name": "Field Sup", "kind": "SUPERVISOR", "keycloak_subject": sup.subject}), 201
    )
    _ok(
        o.post(
            f"{T}/machines/{c.t.machine_id}/assignments",
            {"staff_member_id": staff["id"], "role": "SUPERVISOR", "effective_from": t0.isoformat()},
        ),
        201,
    )
    device = "android-engine-0001"
    headers = {**sup.headers(True, None), "X-Device-Id": device}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=headers, json={"device_id": device, "platform": "ANDROID", "app_version": "1"}
    )
    assert reg.status_code == 201, reg.text

    def push(ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
        r = api.client.post(
            "/api/v1/sync/push",
            headers={**sup.headers(True, None), "X-Device-Id": device},
            json={"device_now": api.clock.now.isoformat(), "operations": ops},
        )
        assert r.status_code == 200, r.text
        out: list[dict[str, Any]] = r.json()["results"]
        return out

    def op(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"id": str(uuid.uuid4()), "op_type": kind, "payload": payload, "created_at_device": t0.isoformat()}

    base = op("METER_BASELINE", {"machine_id": c.t.machine_id, "reading": "70", "captured_at": t0.isoformat()})
    daily = op("METER_CAPTURE", _daily(c.t.machine_id, "72", t0 + timedelta(hours=2)))
    other = api.add_machines(o, 1, prefix="FOREIGN")[0]
    foreign = op("METER_CAPTURE", _daily(other, "5", t0))  # not assigned to this supervisor
    api.clock.set_at(t0 + timedelta(hours=2))
    results = push([base, daily, foreign])
    assert [r["status"] for r in results] == ["ACKED", "ACKED", "REJECTED"]
    assert results[2]["error"]["code"] == "MACHINE_NOT_FOUND"
    assert push([base])[0]["status"] == "DUPLICATE"
    baseline_id = results[0]["result"]["entity"]["id"]
    _ok(
        approver.post(
            f"{T}/meter-baselines/{baseline_id}/decision", {"decision": "APPROVE", "note": "Evidence checked"}
        )
    )
    fix = op(
        "METER_CORRECTION",
        {
            "superseded_capture_id": daily["payload"]["id"],
            "reason": "Second digit misread in the sun",
            "replacement": _daily(c.t.machine_id, "71", t0 + timedelta(hours=2)),
        },
    )
    corrected = push([fix])[0]
    assert corrected["status"] == "ACKED" and corrected["result"]["entity"]["status"] == "PROPOSED"
    assert _ok(o.get(f"{T}/meter-corrections", status="PROPOSED"))["total"] == 1
    assert _ok(sup.get(f"{T}/meter-corrections"))["total"] == 1  # the proposer sees their own
