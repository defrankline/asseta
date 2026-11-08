"""DEC-032 Phase 1: the work allocation ledger, per-day reconciliation, in-job unexplained hours, changeovers, the daily
operational report, value at risk and the unusual-reading flags (guideline 3.2, 4.2, 4.3, T3, T4, scenario 7)."""

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
from tests.support.finance import complete_job, role, setup_finance
from tests.support.hours import RATE, hours_policy, prepaid_job, purchase, verify
from tests.support.intelligence import sweep
from tests.support.jobs import JobCtx, capture, engine_hours_policy, new_job, setup_job
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
                "values": {"opening_mode": "MANUAL", "closing_mode": "MANUAL", "manual_photo_required": False},
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


def _reading(job: str | None, machine: str, kind: str, value: str, at: datetime, **extra: Any) -> dict[str, Any]:
    body = capture(job or "", kind, value, at, mode="MANUAL")
    if job is None:
        body.pop("job_id")
    if kind == "DAILY":
        body["machine_id"] = machine
    return {**body, **extra}


def _ctx(api: Api, name: str) -> tuple[JobCtx, Actor, str]:
    c = setup_job(api, name, name[:6].upper().replace(" ", "") + "-1")
    tid = c.t.tenant["tenant"]["id"]
    _manual_policy(c.owner)
    return c, role(api, tid, "owner", f"approver-{name[:5]}"), tid


def _second_customer(c: JobCtx, api: Api, name: str = "Second Customer") -> tuple[str, str]:
    cust = _ok(c.owner.post(f"{T}/customers", {"code": "C2", "name": name}), 201)["id"]
    contract = _ok(
        c.owner.post(
            f"{T}/contracts", {"customer_id": cust, "contract_number": "CT-2", "starts_on": api.clock.now.isoformat()}
        ),
        201,
    )["id"]
    return cust, contract


def _cancel_setup_job(c: JobCtx) -> None:
    r = c.owner.post(f"{T}/jobs/{c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    assert r.status_code == 200, r.text


def _job(api: Api, c: JobCtx, number: str, contract: str | None = None, rate: str = "1000") -> str:
    saved = c.contract_id
    if contract is not None:
        c.contract_id = contract
    job = new_job(api, c, number, rate=rate)
    c.contract_id = saved
    return job


def _start(c: JobCtx, job: str, reading: str, at: datetime) -> None:
    o = c.owner
    _ok(_cap(o, _reading(job, c.t.machine_id, "OPENING", reading, at)), 201)
    _ok(o.post(f"{T}/jobs/{job}/transitions", {"action": "START"}))


def _close(c: JobCtx, job: str, reading: str, at: datetime) -> None:
    o = c.owner
    _ok(_cap(o, _reading(job, c.t.machine_id, "CLOSING", reading, at)), 201)
    ack = {
        "client_id": str(uuid.uuid4()),
        "method": "NAME_CONFIRMATION",
        "signer_name": "Site Engineer",
        "captured_at": at.isoformat(),
    }
    _ok(o.post(f"{T}/jobs/{job}/acknowledgements", ack), 201)
    _ok(o.post(f"{T}/jobs/{job}/transitions", {"action": "COMPLETE"}))


def _baseline(o: Actor, approver: Actor, c: JobCtx, reading: str, at: datetime) -> None:
    body = {"machine_id": c.t.machine_id, "reading": reading, "captured_at": at.isoformat(), "note": "Initial"}
    proposed = _ok(o.post(f"{T}/meter-baselines", body), 201)
    _ok(approver.post(f"{T}/meter-baselines/{proposed['id']}/decision", {"decision": "APPROVE", "note": "Checked it"}))


def _flags(tid: str, c: JobCtx, kind: str) -> int:
    rows = sql(
        "SELECT count(*) FROM job_exception WHERE tenant_id = :t AND machine_id = :m AND exception_type = :k",
        t=tid,
        m=c.t.machine_id,
        k=kind,
    )
    return int(rows[0][0])


def _allocations(actor: Actor, **params: Any) -> list[dict[str, Any]]:
    return list(_ok(actor.get(f"{T}/work-allocations", **params))["items"])


def _by_kind(rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for r in rows:
        out[r["kind"]] = out.get(r["kind"], Decimal(0)) + Decimal(r["hours"])
    return out


def _day(c: JobCtx, day: date) -> dict[str, Any]:
    params = {"machine_id": c.t.machine_id, "from": day.isoformat(), "to": day.isoformat()}
    rows = _ok(c.owner.get(f"{T}/work-allocations/reconciliation", **params))
    return dict(next(r for r in rows if r["machine_id"] == c.t.machine_id))


def test_ten_hour_day_customer_a_customer_b_and_one_unexplained(api: Api) -> None:
    """Guideline 4.3 example: A 6 h, B 3 h, unexplained 1 h = 10, reconciled with no difference."""
    c, _, _ = _ctx(api, "Ten Hour Co")
    o, t0 = c.owner, api.clock.now
    second_customer, second_contract = _second_customer(c, api)
    _start(c, c.job_id, "1000", t0)
    _close(c, c.job_id, "1006", t0 + timedelta(hours=6))
    job_b = _job(api, c, "J-B", second_contract)
    _start(c, job_b, "1006", t0 + timedelta(hours=6, minutes=1))
    _close(c, job_b, "1009", t0 + timedelta(hours=9))
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "1010", t0 + timedelta(hours=10))), 201)

    rows = _allocations(o, machine_id=c.t.machine_id)
    assert _by_kind(rows) == {"CUSTOMER_WORK": Decimal(9), "UNEXPLAINED": Decimal(1)}
    first_customer = _ok(o.get(f"{T}/contracts/{c.contract_id}"))["customer_id"]
    a = _allocations(o, customer_id=first_customer)
    assert sum(Decimal(r["hours"]) for r in a) == 6
    assert a[0]["customer_name"] and a[0]["job_number"] == "J-001" and a[0]["machine_code"]
    b = _allocations(o, customer_id=second_customer)
    assert sum(Decimal(r["hours"]) for r in b) == 3
    u = _allocations(o, kind="UNEXPLAINED")[0]
    assert (Decimal(u["start_reading"]), Decimal(u["end_reading"])) == (Decimal(1009), Decimal(1010))

    day = _day(c, t0.date())
    assert (Decimal(day["total_engine_hours"]), Decimal(day["difference_hours"])) == (Decimal(10), Decimal(0))
    assert Decimal(day["customer_hours"]) + Decimal(day["unexplained_hours"]) == 10 and day["reconciled"] is True
    one = _ok(o.get(f"{T}/work-allocations/{u['id']}"))
    assert one["status"] == "ACTIVE" and one["recorded_by_name"]


def test_mid_job_changeover_splits_allocation_and_billing_only_when_switched_on(api: Api) -> None:
    c, _, _ = _ctx(api, "Changeover Co")
    o, t0 = c.owner, api.clock.now
    second, _ = _second_customer(c, api)
    _cancel_setup_job(c)
    job = _job(api, c, "J-ONE")
    _start(c, job, "1000", t0)
    change = _reading(job, c.t.machine_id, "DAILY", "1006", t0 + timedelta(hours=6), changeover_to_customer_id=second)
    _ok(_cap(o, change), 201)
    assert _code(_cap(o, {**change, "id": str(uuid.uuid4()), "reading": "1007"})) == "CHANGEOVER_SAME_CUSTOMER"
    _close(c, job, "1009", t0 + timedelta(hours=9))

    b = _allocations(o, customer_id=second)
    assert sum(Decimal(r["hours"]) for r in b) == 3 and b[0]["changeover_id"] is not None and b[0]["job_id"] == job
    assert Decimal(_ok(o.get(f"{T}/jobs/{job}"))["billable_hours"]) == 9  # billing unchanged by default

    # Switched on (for jobs started from now on): the hours after the changeover leave the job's billing.
    engine_hours_policy(o, changeover_splits_billing=True)
    later = t0 + timedelta(hours=10)
    job2 = _job(api, c, "J-TWO")
    _start(c, job2, "1009", later)
    change2 = _reading(
        job2, c.t.machine_id, "DAILY", "1015", later + timedelta(hours=6), changeover_to_customer_id=second
    )
    _ok(_cap(o, change2), 201)
    _close(c, job2, "1018", later + timedelta(hours=9))
    assert Decimal(_ok(o.get(f"{T}/jobs/{job2}"))["billable_hours"]) == 6


def test_in_job_uncovered_hours_are_unexplained_and_not_billed_when_policy_is_off(api: Api) -> None:
    c, approver, _ = _ctx(api, "In Job Co")
    o, t0 = c.owner, api.clock.now
    _cancel_setup_job(c)
    default_job = _job(api, c, "J-DEFAULT")
    _start(c, default_job, "1000", t0)
    _close(c, default_job, "1003", t0 + timedelta(hours=3))
    assert _by_kind(_allocations(o, job_id=default_job)) == {"CUSTOMER_WORK": Decimal(3)}

    _baseline(o, approver, c, "999", t0 - timedelta(hours=1))
    engine_hours_policy(o, in_job_time_counts_as_customer_work=False)
    later = t0 + timedelta(hours=4)
    job = _job(api, c, "J-COVERED")
    _start(c, job, "1003", later)
    _ok(
        o.post(
            f"{T}/jobs/{job}/activities",
            {
                "client_id": str(uuid.uuid4()),
                "activity_type": "WORK",
                "started_at": later.isoformat(),
                "ended_at": (later + timedelta(hours=5)).isoformat(),
            },
        ),
        201,
    )
    _close(c, job, "1009", later + timedelta(hours=6))
    assert _by_kind(_allocations(o, job_id=job)) == {"CUSTOMER_WORK": Decimal(5), "UNEXPLAINED": Decimal(1)}
    assert Decimal(_ok(o.get(f"{T}/jobs/{job}"))["billable_hours"]) == 5  # the uncovered hour is not billable
    open_items = _ok(o.get(f"{T}/engine-hours/unallocated", machine_id=c.t.machine_id))["items"]
    assert Decimal(1) in [Decimal(i["hours"]) for i in open_items if i["classification"] == "UNEXPLAINED"]


def test_scenario_seven_unexplained_is_flagged_not_billable_not_wasted(api: Api) -> None:
    c, approver, tid = _ctx(api, "Scenario Seven")
    o, t0 = c.owner, api.clock.now
    _ok(
        o.post(
            f"{T}/policies/REVENUE_RECONCILIATION/versions",
            {"scope": "TENANT", "values": {"enabled": True, "period": "DAY"}, "reason": "On for test"},
        ),
        201,
    )
    _ok(
        o.post(
            f"{T}/meter-baselines",
            {
                "machine_id": c.t.machine_id,
                "reading": "1000",
                "captured_at": (t0 - timedelta(hours=1)).isoformat(),
                "note": "Base",
            },
        ),
        201,
    )
    baseline = _ok(o.get(f"{T}/meter-baselines"))["items"][0]["id"]
    _ok(approver.post(f"{T}/meter-baselines/{baseline}/decision", {"decision": "APPROVE", "note": "Evidence checked"}))
    _cancel_setup_job(c)
    job = _job(api, c, "J-S7", rate="85000")
    _start(c, job, "1000", t0)
    _close(c, job, "1004", t0 + timedelta(hours=4))
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "1006", t0 + timedelta(hours=6))), 201)

    assert _flags(tid, c, "UNEXPLAINED_HOURS") == 1
    assert _by_kind(_allocations(o, kind="UNEXPLAINED")) == {"UNEXPLAINED": Decimal(2)}
    row = _ok(o.get(f"{T}/daily-machine-sheet", day_from=t0.date(), day_to=t0.date()))["items"][0]
    money = row["money"][0]
    assert Decimal(money["unexplained_hours"]) == 2 and Decimal(money["unexplained_expected"]) == 0
    assert Decimal(money["value_at_risk"]) == 2 * Decimal(85000)  # machine rate card, separate line
    assert Decimal(money["expected"]) == 4 * Decimal(85000)  # expected only from the job: never unexplained hours
    assert Decimal(money["difference"]) == Decimal(money["expected"]) - Decimal(money["attributed"])
    assert Decimal(money["difference"]) >= 0
    tile = _ok(o.get(f"{T}/accountability/summary"))["unexplained_hours"]
    assert Decimal(tile["hours"]) == 2 and Decimal(tile["value_at_risk"][0]["amount"]) == 2 * Decimal(85000)


def test_corrections_supersede_never_edit_and_need_a_second_person(api: Api) -> None:
    c, approver, _ = _ctx(api, "Correct Co")
    o, t0 = c.owner, api.clock.now
    reason = _ok(
        o.post(f"{T}/engine-hour-reasons", {"kind": "NON_CUSTOMER_CATEGORY", "code": "MAINT", "name": "Maintenance"}),
        201,
    )["id"]
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "2000", t0)), 201)
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "2004", t0 + timedelta(hours=4))), 201)
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
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "500", t0)), 201)
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "505", t0 + timedelta(hours=5))), 201)
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
    first = _reading(None, c.t.machine_id, "DAILY", "3000", t0)
    last = _reading(None, c.t.machine_id, "DAILY", "3008", t0 + timedelta(hours=8))
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
    assert _flags(tid, c, "DUPLICATE_DAILY_REPORT") == 1

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
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "102", t0 + timedelta(hours=2))), 201)
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "105", t0 + timedelta(hours=5))), 201)
    sweep(api, tid)
    signals = sql(
        "SELECT evidence FROM risk_signal WHERE tenant_id = :t AND rule_code = 'UNEXPLAINED_ENGINE_HOURS'", t=tid
    )
    assert any(s[0].get("basis") == "AMOUNT" and Decimal(s[0]["hours"]) == 5 for s in signals)

    r = _cap(o, _reading(None, c.t.machine_id, "DAILY", "101", t0 + timedelta(hours=6)))
    findings = _ok(r, 201)["findings"]
    decrease = next(f for f in findings if f["type"] == "METER_DECREASE")
    assert decrease["evidence"]["label"] == "POSSIBLE_METER_RESET"


def test_prepaid_allocation_links_lots_with_per_lot_hours(api: Api) -> None:
    f = setup_finance(api)
    hours_policy(f, walk_in_allowed=True)
    p1 = purchase(api, f.accountant, f, "3", pay=str(3 * RATE))
    p2 = purchase(api, f.accountant, f, "20", pay=str(20 * RATE))
    verify(f.accountant2, p1["payment"]["id"])
    verify(f.accountant2, p2["payment"]["id"])
    r = f.owner.post(f"{T}/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    assert r.status_code == 200, r.text
    job = prepaid_job(api, f, "P-LOTS")
    complete_job(api, f, job, "1000", "1005", 5)
    [entry] = _allocations(f.owner, job_id=job)
    assert entry["kind"] == "CUSTOMER_WORK" and Decimal(entry["hours"]) == 5
    lots = {lot["purchase_id"]: Decimal(lot["hours"]) for lot in entry["lots"]}
    assert lots == {p1["id"]: Decimal(3), p2["id"]: Decimal(2)}
    assert all(lot["purchase_number"] for lot in entry["lots"])
