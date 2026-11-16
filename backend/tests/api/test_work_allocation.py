"""DEC-032 Phase 1: the work allocation ledger, per-day reconciliation, the daily operational report, value at risk
and the unusual-reading flags (guideline 3.2, 4.2, 4.3, T3, T4, scenario 7). Customer hours enter the ledger when a
machine report is approved (ADR-008); hours no report accounts for are UNEXPLAINED until someone explains them."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InternalError, ProgrammingError

from asseta.core.db import get_sessionmaker
from asseta.modules.meter.allocation_writer import run_work_allocations
from tests.support.api import Actor, Api
from tests.support.finance import role
from tests.support.intelligence import sweep
from tests.support.machine_reports import ReportCtx, bought, cust, customer, report_body, setup_reports, submit
from tests.support.meter import MachineCtx, capture, engine_hours_policy, setup_machine, unique_jpeg
from tests.support.notify import sql

T = "/api/v1/tenant"
DEVICE = "android-allocation-1"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _code(r: Any) -> str:
    return str(r.json()["error"]["code"])


def _manual_policy(owner: Actor) -> None:
    _ok(
        owner.post(
            f"{T}/policies/METER_CAPTURE/versions",
            {
                "scope": "TENANT",
                "values": {"capture_mode": "MANUAL", "manual_photo_required": False},
                "reason": "Manual capture for allocation tests",
            },
        ),
        201,
    )


def _cap(actor: Actor, body: dict[str, Any]) -> Any:
    at = datetime.fromisoformat(body["captured_at"])
    if at > actor.api.clock.now:
        actor.api.clock.set_at(at)
    return actor.post(f"{T}/meter-captures", body)


def _reading(machine: str, value: str, at: datetime, **extra: Any) -> dict[str, Any]:
    return {**capture(machine, value, at, mode="MANUAL"), **extra}


def _ctx(api: Api, name: str) -> tuple[MachineCtx, Actor, str]:
    c = setup_machine(api, name, name[:6].upper().replace(" ", "") + "-1")
    tid = c.t.tenant["tenant"]["id"]
    _manual_policy(c.owner)
    return c, role(api, tid, "owner", f"approver-{name[:5]}"), tid


def _approved_report(api: Api, ctx: ReportCtx, value: str, at: datetime, lines: list[dict[str, Any]]) -> Any:
    api.clock.set_at(at)
    rep = submit(ctx.f.supervisor, report_body(ctx.machine_id, value, at, lines))
    return _ok(ctx.f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))


def _baseline(o: Actor, approver: Actor, c: MachineCtx, reading: str, at: datetime) -> None:
    body = {"machine_id": c.t.machine_id, "reading": reading, "captured_at": at.isoformat(), "note": "Initial"}
    proposed = _ok(o.post(f"{T}/meter-baselines", body), 201)
    _ok(approver.post(f"{T}/meter-baselines/{proposed['id']}/decision", {"decision": "APPROVE", "note": "Checked it"}))


def _flags(tid: str, machine_id: str, kind: str, status: str | None = None) -> int:
    rows = sql(
        "SELECT count(*) FROM meter_exception WHERE tenant_id = :t AND machine_id = :m AND exception_type = :k"
        " AND (CAST(:s AS text) IS NULL OR status = :s)",
        t=tid,
        m=machine_id,
        k=kind,
        s=status,
    )
    return int(rows[0][0])


def _allocations(actor: Actor, **params: Any) -> list[dict[str, Any]]:
    return list(_ok(actor.get(f"{T}/work-allocations", **params))["items"])


def _by_kind(rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for r in rows:
        out[r["kind"]] = out.get(r["kind"], Decimal(0)) + Decimal(r["hours"])
    return out


def _day(actor: Actor, machine_id: str, day: date) -> dict[str, Any]:
    params = {"machine_id": machine_id, "from": day.isoformat(), "to": day.isoformat()}
    rows = _ok(actor.get(f"{T}/work-allocations/reconciliation", **params))
    return dict(next(r for r in rows if r["machine_id"] == machine_id))


def test_ten_hour_day_customer_a_customer_b_and_one_unexplained(api: Api) -> None:
    """Guideline 4.3 example: A 6 h, B 3 h, unexplained 1 h = 10, reconciled with no difference."""
    ctx = setup_reports(api, "Ten Hour Co", "TENHR-1")  # baseline 1000 two hours ago
    f, m = ctx.f, ctx.machine_id
    o, t0 = f.owner, api.clock.now
    second = customer(f, "C2", "Second Customer")
    bought(api, f, 6)
    bought(api, f, 3, customer_id=second)
    rep = _approved_report(api, ctx, "1009", t0 + timedelta(hours=7), [cust(f.customer_id, 6), cust(second, 3)])
    _ok(_cap(o, _reading(m, "1010", t0 + timedelta(hours=8))), 201)

    rows = _allocations(o, machine_id=m)
    assert _by_kind(rows) == {"CUSTOMER_WORK": Decimal(9), "UNEXPLAINED": Decimal(1)}
    a = _allocations(o, customer_id=f.customer_id)
    assert sum(Decimal(r["hours"]) for r in a) == 6
    assert a[0]["customer_name"] and a[0]["machine_code"] and a[0]["source"] == "MACHINE_REPORT"
    assert a[0]["approval_ref_ids"] == [rep["id"]]
    b = _allocations(o, customer_id=second)
    assert sum(Decimal(r["hours"]) for r in b) == 3
    u = _allocations(o, kind="UNEXPLAINED")[0]
    assert (Decimal(u["start_reading"]), Decimal(u["end_reading"])) == (Decimal(1009), Decimal(1010))

    day = _day(o, m, date.fromisoformat(u["work_date"]))
    assert (Decimal(day["total_engine_hours"]), Decimal(day["difference_hours"])) == (Decimal(10), Decimal(0))
    assert Decimal(day["customer_hours"]) + Decimal(day["unexplained_hours"]) == 10 and day["reconciled"] is True
    one = _ok(o.get(f"{T}/work-allocations/{u['id']}"))
    assert one["status"] == "ACTIVE" and one["recorded_by_name"]


def test_field_gets_reasons_time_zone_and_policy(api: Api) -> None:
    ctx = setup_reports(api, "Field Lists", "FLD-1")
    o, sup = ctx.f.owner, ctx.f.supervisor
    reason = _ok(o.post(f"{T}/engine-hour-reasons", {"kind": "UNBILLABLE_REASON", "code": "RAIN", "name": "Rain"}), 201)
    _ok(o.post(f"{T}/engine-hour-reasons", {"kind": "NON_CUSTOMER_CATEGORY", "code": "YARD", "name": "Yard"}), 201)
    device = "android-field-lists-1"
    headers = {**sup.headers(True, None), "X-Device-Id": device}
    _ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=headers,
            json={"device_id": device, "platform": "ANDROID", "app_version": "1"},
        ),
        201,
    )
    boot = _ok(api.client.get("/api/v1/sync/bootstrap", headers=headers))
    assert boot["tenant_timezone"] == "Africa/Dar_es_Salaam"
    assert "SYNC_UNBILLABLE_REASONS" in boot["capabilities"]
    assert [r["id"] for r in boot["data"]["unbillable_reasons"]] == [reason["id"]]

    body = {"reason": "No longer used", "version": reason["version"]}
    _ok(o.post(f"{T}/engine-hour-reasons/{reason['id']}/deactivate", body))
    changes = _ok(api.client.get("/api/v1/sync/changes", headers=headers, params={"cursor": boot["cursor"]}))
    assert changes["tenant_timezone"] == "Africa/Dar_es_Salaam"
    assert [(r["id"], r["is_active"]) for r in changes["data"]["unbillable_reasons"]] == [(reason["id"], False)]

    # The field can read the rules it must follow, and upload a daily report's evidence online.
    assert "daily_report_required" in _ok(sup.get(f"{T}/policies/ENGINE_HOURS/effective"))["values"]
    upload = api.client.post(
        f"{T}/attachments",
        headers=sup.headers(True, None),
        files={"file": ("r.jpg", unique_jpeg(), "image/jpeg")},
        data={"purpose": "DAILY_REPORT_EVIDENCE"},
    )
    assert upload.status_code == 201, upload.text


def test_scenario_seven_unexplained_is_flagged_not_billable_not_wasted(api: Api) -> None:
    ctx = setup_reports(api, "Scenario Seven", "SCEN7-1")  # rate card 85,000 / hour for the machine's category
    f, m = ctx.f, ctx.machine_id
    o, t0 = f.owner, api.clock.now
    bought(api, f, 4)
    _approved_report(api, ctx, "1004", t0 + timedelta(hours=2), [cust(f.customer_id, 4)])
    _ok(_cap(o, _reading(m, "1006", t0 + timedelta(hours=4))), 201)

    assert _flags(f.tid, m, "UNEXPLAINED_HOURS", "OPEN") == 1  # the report's own hours are accounted for
    assert _by_kind(_allocations(o, kind="UNEXPLAINED")) == {"UNEXPLAINED": Decimal(2)}
    assert _by_kind(_allocations(o, kind="CUSTOMER_WORK")) == {"CUSTOMER_WORK": Decimal(4)}  # only reported hours
    tile = _ok(o.get(f"{T}/accountability/summary"))["unexplained_hours"]
    assert Decimal(tile["hours"]) == 2 and Decimal(tile["value_at_risk"][0]["amount"]) == 2 * Decimal(85000)


def test_corrections_supersede_never_edit_and_need_a_second_person(api: Api) -> None:
    c, approver, _ = _ctx(api, "Correct Co")
    o, t0 = c.owner, api.clock.now
    reason = _ok(
        o.post(f"{T}/engine-hour-reasons", {"kind": "NON_CUSTOMER_CATEGORY", "code": "MAINT", "name": "Maintenance"}),
        201,
    )["id"]
    _ok(_cap(o, _reading(c.t.machine_id, "2000", t0)), 201)
    _ok(_cap(o, _reading(c.t.machine_id, "2004", t0 + timedelta(hours=4))), 201)
    [entry] = _allocations(o, machine_id=c.t.machine_id)
    url = f"{T}/work-allocations/{entry['id']}/corrections"
    bad = {"parts": [{"hours": "3", "kind": "UNEXPLAINED"}], "reason": "Wrong kind recorded"}
    assert _code(o.post(url, bad)) == "ALLOCATION_PARTS_MISMATCH"
    body = {
        "parts": [
            {"hours": "3", "kind": "AUTHORIZED_ACTIVITY", "reason_id": reason},
            {"hours": "1", "kind": "UNEXPLAINED"},
        ],
        "reason": "Three hours were maintenance",
    }
    proposal = _ok(o.post(url, body), 201)
    assert proposal["status"] == "PROPOSED" and len(proposal["entries"]) == 2
    assert _code(o.post(url, body)) == "ALLOCATION_CORRECTION_PENDING"
    group = proposal["group_id"]
    decide = f"{T}/work-allocations/corrections/{group}/decision"
    assert _code(o.post(decide, {"decision": "APPROVE", "note": "Self approval"})) == "SEGREGATION_OF_DUTIES"
    done = _ok(approver.post(decide, {"decision": "APPROVE", "note": "Maintenance log checked"}))
    assert done["status"] == "ACTIVE" and _ok(o.get(f"{T}/work-allocations/corrections/{group}"))["status"] == "ACTIVE"

    original = _ok(o.get(f"{T}/work-allocations/{entry['id']}"))
    assert original["status"] == "SUPERSEDED" and len(original["superseded_by_ids"]) == 2
    assert done["entries"][0]["approval_ref_type"] == "work_allocation_correction"
    assert done["entries"][0]["approval_ref_ids"] == [group]
    assert _by_kind(_allocations(o, machine_id=c.t.machine_id)) == {
        "AUTHORIZED_ACTIVITY": Decimal(3),
        "UNEXPLAINED": Decimal(1),
    }
    assert _allocations(o, machine_id=c.t.machine_id, kind="AUTHORIZED_ACTIVITY")[0]["reason_name"] == "Maintenance"

    summary = run_work_allocations(get_sessionmaker(), api.clock.now)  # the sweep keeps the approved correction
    assert summary.written == 0 and summary.superseded == 0
    assert _by_kind(_allocations(o, machine_id=c.t.machine_id))["AUTHORIZED_ACTIVITY"] == 3

    # Directly applied when the tenant does not require a second person.
    engine_hours_policy(o, allocation_correction_requires_approval=False)
    unexplained = _allocations(o, kind="UNEXPLAINED")[0]
    direct = _ok(
        o.post(
            f"{T}/work-allocations/{unexplained['id']}/corrections",
            {
                "parts": [{"hours": "1", "kind": "AUTHORIZED_ACTIVITY", "reason_id": reason}],
                "reason": "Also maintenance",
            },
        ),
        201,
    )
    assert direct["status"] == "ACTIVE"


def test_database_refuses_overlap_and_guards_the_ledger(api: Api, owner_engine: Any) -> None:
    c, _, _ = _ctx(api, "Guard Co")
    o, t0 = c.owner, api.clock.now
    _ok(_cap(o, _reading(c.t.machine_id, "500", t0)), 201)
    _ok(_cap(o, _reading(c.t.machine_id, "505", t0 + timedelta(hours=5))), 201)
    [entry] = _allocations(o, machine_id=c.t.machine_id)

    def run(statement: str, **params: Any) -> None:
        with owner_engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.scope', 'system', true)"))
            conn.execute(text(statement), params)

    with pytest.raises(IntegrityError):
        run(
            "INSERT INTO work_allocation (id, tenant_id, machine_id, work_date, start_ref, start_reading, start_at,"
            " end_ref, end_reading, end_at, meter_epoch, hours, kind, reading_review, lots, evidence_attachment_ids,"
            " source, status, origin_key, origin_hours, policy_version, created_at)"
            " SELECT gen_random_uuid(), tenant_id, machine_id, work_date, start_ref, 502, start_at, end_ref, 503, end_at,"
            " meter_epoch, 1, kind, reading_review, '[]', '{}', source, 'ACTIVE', 'x', 1, policy_version, created_at"
            " FROM work_allocation WHERE id = :i",
            i=entry["id"],
        )
    for stmt in (
        "UPDATE work_allocation SET hours = 1 WHERE id = :i",
        "DELETE FROM work_allocation WHERE id = :i",
    ):
        with pytest.raises((InternalError, ProgrammingError)):
            run(stmt, i=entry["id"])


def test_daily_report_flow(api: Api) -> None:
    c, approver, tid = _ctx(api, "Daily Report Co")
    o, t0 = c.owner, api.clock.now
    reason = _ok(
        o.post(f"{T}/engine-hour-reasons", {"kind": "UNBILLABLE_REASON", "code": "RAIN", "name": "Rain stoppage"}), 201
    )["id"]
    first = _reading(c.t.machine_id, "3000", t0)
    last = _reading(c.t.machine_id, "3008", t0 + timedelta(hours=8))
    _ok(_cap(o, first), 201)
    _ok(_cap(o, last), 201)
    day = t0.date()
    pre = _ok(o.get(f"{T}/daily-reports/prefill", machine_id=c.t.machine_id, report_date=day))
    assert pre["opening_ref"] == first["id"] and pre["closing_ref"] == last["id"] and Decimal(pre["total_hours"]) == 8
    assert Decimal(pre["unexplained_hours"]) == 8 and pre["existing_report_ids"] == []
    body = {
        "id": str(uuid.uuid4()),
        "machine_id": c.t.machine_id,
        "report_date": day.isoformat(),
        "opening_ref": first["id"],
        "closing_ref": last["id"],
        "billable_hours": "5",
        "unbillable": [{"reason_id": reason, "hours": "2"}],
        "note": "Rain stopped work at noon",
        "client_created_at": (t0 + timedelta(hours=8)).isoformat(),
    }
    report = _ok(o.post(f"{T}/daily-reports", body), 201)
    assert Decimal(report["total_hours"]) == 8 and Decimal(report["difference_hours"]) == 1
    assert report["status"] == "SUBMITTED" and report["unbillable"][0]["reason_name"] == "Rain stoppage"
    assert report["allocations"] and report["machine_code"]
    assert _ok(o.post(f"{T}/daily-reports", body), 201)["id"] == report["id"]  # idempotent retry

    too_much = {**body, "id": str(uuid.uuid4()), "billable_hours": "9"}
    assert _code(o.post(f"{T}/daily-reports", too_much)) == "REPORT_HOURS_EXCEED_TOTAL"
    bad_reason = {**body, "id": str(uuid.uuid4()), "unbillable": [{"reason_id": str(uuid.uuid4()), "hours": "1"}]}
    assert _code(o.post(f"{T}/daily-reports", bad_reason)) == "REASON_NOT_ALLOWED"

    # Repeat for the same machine-day: kept and flagged, never overwritten.
    repeat = _ok(o.post(f"{T}/daily-reports", {**body, "id": str(uuid.uuid4())}), 201)
    assert repeat["is_duplicate"] is True and repeat["duplicate_of_id"] == report["id"]
    assert _flags(tid, c.t.machine_id, "DUPLICATE_DAILY_REPORT") == 1

    review = f"{T}/daily-reports/{report['id']}/review"
    assert _code(o.post(review, {"decision": "REVIEWED", "note": "My own report"})) == "SEGREGATION_OF_DUTIES"
    returned = _ok(approver.post(review, {"decision": "RETURNED", "note": "Add the rain photo"}))
    assert returned["status"] == "RETURNED" and returned["reviewed_by_name"]
    assert _code(approver.post(review, {"decision": "REVIEWED", "note": "Trying again"})) == "REPORT_ALREADY_REVIEWED"
    # The resubmission supersedes the returned report (the original stays).
    fixed = _ok(o.post(f"{T}/daily-reports", {**body, "id": str(uuid.uuid4()), "supersedes_id": report["id"]}), 201)
    assert fixed["supersedes_id"] == report["id"]
    assert _ok(o.get(f"{T}/daily-reports/{report['id']}"))["status"] == "SUPERSEDED"
    assert (
        _ok(approver.post(f"{T}/daily-reports/{fixed['id']}/review", {"decision": "REVIEWED", "note": "Looks right"}))[
            "status"
        ]
        == "REVIEWED"
    )
    assert _ok(o.get(f"{T}/daily-reports", machine_id=c.t.machine_id, status="REVIEWED"))["total"] == 1

    # Offline: DAILY_REPORT with the operation id as the report id; a retry returns the stored result.
    headers = {**o.headers(True, None), "X-Device-Id": DEVICE}
    _ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=headers,
            json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1"},
        ),
        201,
    )
    op_id = str(uuid.uuid4())
    payload = {k: v for k, v in body.items() if k not in ("id", "note")}
    op = {
        "id": op_id,
        "op_type": "DAILY_REPORT",
        "payload": payload,
        "created_at_device": t0.isoformat(),
        "depends_on": [],
    }

    def push() -> dict[str, Any]:
        r = api.client.post(
            "/api/v1/sync/push", headers=headers, json={"device_now": api.clock.now.isoformat(), "operations": [op]}
        )
        assert r.status_code == 200, r.text
        return dict(r.json()["results"][0])

    first_push = push()
    assert first_push["status"] == "ACKED" and first_push["result"]["entity"]["id"] == op_id
    assert push()["status"] == "DUPLICATE"
    assert "OP_DAILY_REPORT" in _ok(api.client.get("/api/v1/sync/bootstrap", headers=headers))["capabilities"]

    # The capability switched off: refused offline with the capability's code.
    engine_hours_policy(o, enabled=False)
    other = {**op, "id": str(uuid.uuid4())}
    r = api.client.post(
        "/api/v1/sync/push", headers=headers, json={"device_now": api.clock.now.isoformat(), "operations": [other]}
    )
    assert (
        r.json()["results"][0]["status"] == "CONFLICT"
        and r.json()["results"][0]["error"]["code"] == "ENGINE_HOURS_DISABLED"
    )


def test_amount_threshold_opens_investigation_and_decrease_is_labelled_possible_reset(api: Api) -> None:
    c, approver, tid = _ctx(api, "Amount Co")
    o, t0 = c.owner, api.clock.now
    engine_hours_policy(o, unexplained_flag_amount_hours="3", unexplained_investigation_after_days=None)
    _ok(
        o.post(
            f"{T}/meter-baselines",
            {
                "machine_id": c.t.machine_id,
                "reading": "100",
                "captured_at": (t0 - timedelta(hours=1)).isoformat(),
                "note": "Base",
            },
        ),
        201,
    )
    baseline = _ok(o.get(f"{T}/meter-baselines"))["items"][0]["id"]
    _ok(approver.post(f"{T}/meter-baselines/{baseline}/decision", {"decision": "APPROVE", "note": "Evidence checked"}))
    _ok(_cap(o, _reading(c.t.machine_id, "102", t0 + timedelta(hours=2))), 201)
    _ok(_cap(o, _reading(c.t.machine_id, "105", t0 + timedelta(hours=5))), 201)
    sweep(api, tid)
    signals = sql(
        "SELECT evidence FROM risk_signal WHERE tenant_id = :t AND rule_code = 'UNEXPLAINED_ENGINE_HOURS'", t=tid
    )
    assert any(s[0].get("basis") == "AMOUNT" and Decimal(s[0]["hours"]) == 5 for s in signals)

    r = _cap(o, _reading(c.t.machine_id, "101", t0 + timedelta(hours=6)))
    findings = _ok(r, 201)["findings"]
    decrease = next(f for f in findings if f["type"] == "METER_DECREASE")
    assert decrease["evidence"]["label"] == "POSSIBLE_METER_RESET"


def test_approved_report_allocation_links_lots_with_per_lot_hours(api: Api) -> None:
    ctx = setup_reports(api, "Lots Co", "LOTS-1")
    f, m = ctx.f, ctx.machine_id
    p1 = bought(api, f, 3)
    p2 = bought(api, f, 20)
    _approved_report(api, ctx, "1005", api.clock.now + timedelta(hours=4), [cust(f.customer_id, 5)])
    [entry] = _allocations(f.owner, machine_id=m, kind="CUSTOMER_WORK")
    assert Decimal(entry["hours"]) == 5
    lots = {lot["purchase_id"]: Decimal(lot["hours"]) for lot in entry["lots"]}
    assert lots == {p1["id"]: Decimal(3), p2["id"]: Decimal(2)}
    assert all(lot["purchase_number"] for lot in entry["lots"])
