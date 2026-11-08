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
from tests.support.finance import complete_job, issue_invoice, role, setup_finance
from tests.support.hours import RATE, balance, hours_policy, prepaid_job, purchase, verify
from tests.support.intelligence import sweep
from tests.support.jobs import JobCtx, capture, engine_hours_policy, new_job, setup_job, unique_jpeg
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


def _pending_job(c: JobCtx, number: str, contract: str, rate: str = "1000", mode: str | None = None) -> str:
    body: dict[str, Any] = {
        "contract_id": contract,
        "job_number": number,
        "machine_id": c.t.machine_id,
        "planned_start": c.owner.api.clock.now.isoformat(),
        "hourly_rate": rate,
    }
    if mode is not None:
        body["billing_mode"] = mode
    job = str(_ok(c.owner.post(f"{T}/jobs", body), 201)["id"])
    _ok(c.owner.post(f"{T}/jobs/{job}/transitions", {"action": "SUBMIT"}))
    return job


def _hire(summary: dict[str, Any]) -> Decimal:
    return sum((Decimal(x["quantity"]) for x in summary["charges"]["lines"] if x["kind"] == "HIRE"), Decimal(0))


def test_changeover_without_a_job_is_a_sync_conflict_when_billing_is_split(api: Api) -> None:
    c, _, _ = _ctx(api, "Split Sync")
    o, t0 = c.owner, api.clock.now
    second, _ = _second_customer(c, api)
    engine_hours_policy(o, changeover_splits_billing=True)
    _start(c, c.job_id, "1000", t0)
    headers = {**o.headers(True, None), "X-Device-Id": DEVICE}
    _ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=headers,
            json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1"},
        ),
        201,
    )
    at = t0 + timedelta(hours=6)
    api.clock.set_at(at)
    payload = _reading(c.job_id, c.t.machine_id, "DAILY", "1006", at, changeover_to_customer_id=second)
    op = {
        "id": str(uuid.uuid4()),
        "op_type": "METER_CAPTURE",
        "payload": payload,
        "created_at_device": at.isoformat(),
        "depends_on": [],
    }
    r = _ok(
        api.client.post("/api/v1/sync/push", headers=headers, json={"device_now": at.isoformat(), "operations": [op]})
    )
    assert (r["results"][0]["status"], r["results"][0]["error"]["code"]) == ("CONFLICT", "CHANGEOVER_JOB_REQUIRED")


def _changed_over(api: Api, c: JobCtx, b_contract: str, second: str, mode: str | None = None) -> tuple[str, datetime]:
    """Job A runs 1000-1009 with a changeover at 1006 naming pending job B; B is then approved and runs 1009-1010."""
    o, t0 = c.owner, api.clock.now
    engine_hours_policy(o, changeover_splits_billing=True)
    a = c.job_id
    job_b = _pending_job(c, "J-NEXT", b_contract, mode=mode)
    _start(c, a, "1000", t0)
    moved = _reading(a, c.t.machine_id, "DAILY", "1006", t0 + timedelta(hours=6), changeover_to_customer_id=second)
    assert _code(_cap(o, moved)) == "CHANGEOVER_JOB_REQUIRED"
    assert _code(_cap(o, {**moved, "id": str(uuid.uuid4()), "changeover_to_job_id": a})) == "CHANGEOVER_JOB_INVALID"
    _ok(_cap(o, {**moved, "id": str(uuid.uuid4()), "changeover_to_job_id": job_b}), 201)
    _close(c, a, "1009", t0 + timedelta(hours=9))
    refused = o.post(f"{T}/jobs/{job_b}/transitions", {"action": "CANCEL", "reason": "Not needed after all"})
    assert _code(refused) == "JOB_HAS_CHANGEOVER_HOURS"  # those hours must keep a job to bill
    _ok(o.post(f"{T}/jobs/{job_b}/transitions", {"action": "APPROVE"}))
    _start(c, job_b, "1009", t0 + timedelta(hours=9, minutes=1))
    _close(c, job_b, "1010", t0 + timedelta(hours=10))
    return job_b, t0


def test_changeover_with_billing_split_bills_the_named_job_invoice(api: Api) -> None:
    f = setup_finance(api, "Split Invoice", "SPLIT-1")
    c, o = f.c, f.owner
    second, contract = _second_customer(c, api)
    job_b, t0 = _changed_over(api, c, contract, second)

    a_summary, b_summary = _ok(o.get(f"{T}/jobs/{c.job_id}")), _ok(o.get(f"{T}/jobs/{job_b}"))
    assert (Decimal(a_summary["billable_hours"]), Decimal(b_summary["billable_hours"])) == (Decimal(6), Decimal(4))
    assert Decimal(b_summary["changeover_carried_hours"]) == 3  # A loses exactly what B gains
    assert _hire(a_summary) + _hire(b_summary) == 10  # every engine hour is billed exactly once

    # The allocation ledger agrees: A's job holds 6 h for A's customer, B's job 3 + 1 h for B's.
    assert sum(Decimal(r["hours"]) for r in _allocations(o, job_id=c.job_id)) == 6
    b_rows = _allocations(o, job_id=job_b)
    assert sum(Decimal(r["hours"]) for r in b_rows) == 4 and {r["customer_id"] for r in b_rows} == {second}
    day = _day(c, t0.date())
    assert (Decimal(day["total_engine_hours"]), Decimal(day["customer_hours"])) == (Decimal(10), Decimal(10))
    assert Decimal(day["difference_hours"]) == 0

    invoice_a = issue_invoice(f, [c.job_id])
    draft = _ok(f.accountant.post(f"{T}/hire-invoices", {"customer_id": second, "job_ids": [job_b]}), 201)
    invoice_b = _ok(f.accountant.post(f"{T}/hire-invoices/{draft['id']}/issue", {}))
    quantity = [
        sum(Decimal(x["quantity"]) for x in inv["lines"] if x["kind"] == "HIRE") for inv in (invoice_a, invoice_b)
    ]
    assert quantity == [Decimal(6), Decimal(4)]


def test_changeover_with_billing_split_draws_the_named_jobs_prepaid_hours(api: Api) -> None:
    f = setup_finance(api, "Split Prepaid", "SPLIT-2")
    c, o = f.c, f.owner
    second, contract = _second_customer(c, api)
    lot = purchase(api, f.accountant, f, "10", customer_id=second, pay=str(10 * RATE))
    verify(f.accountant2, lot["payment"]["id"])
    job_b, _ = _changed_over(api, c, contract, second, mode="PREPAID_HOURS")

    assert Decimal(_ok(o.get(f"{T}/jobs/{c.job_id}"))["billable_hours"]) == 6
    wea = _ok(o.get(f"{T}/work-execution-allocations", job_id=job_b))["items"][0]
    assert (Decimal(wea["billable_hours"]), Decimal(wea["consumed_hours"])) == (Decimal(4), Decimal(4))
    bal = balance(o, second, c.t.machine_id)
    assert bal is not None and Decimal(bal["remaining"]) == 6
    rows = _allocations(o, job_id=job_b)
    assert sum(Decimal(x["hours"]) for r in rows for x in r["lots"]) == 4  # the lots agree with the allocation
    assert {x["purchase_id"] for r in rows for x in r["lots"]} == {lot["id"]}


def test_time_already_deducted_is_not_moved_to_the_next_job(api: Api) -> None:
    """One hour of downtime after the changeover stays deducted: A and B plus that hour still equal the engine hours."""
    f = setup_finance(api, "Split Downtime", "SPLIT-3")
    c, o = f.c, f.owner
    second, contract = _second_customer(c, api)
    engine_hours_policy(o, changeover_splits_billing=True)
    t0 = api.clock.now
    job_b = _pending_job(c, "J-NEXT", contract)
    _start(c, c.job_id, "1000", t0)
    moved = _reading(
        c.job_id,
        c.t.machine_id,
        "DAILY",
        "1006",
        t0 + timedelta(hours=6),
        changeover_to_customer_id=second,
        changeover_to_job_id=job_b,
    )
    _ok(_cap(o, moved), 201)
    down = {
        "client_id": str(uuid.uuid4()),
        "activity_type": "DOWNTIME",
        "started_at": (t0 + timedelta(hours=7)).isoformat(),
        "ended_at": (t0 + timedelta(hours=8)).isoformat(),
        "billable": False,
    }
    _ok(o.post(f"{T}/jobs/{c.job_id}/activities", down), 201)
    _close(c, c.job_id, "1009", t0 + timedelta(hours=9))
    _ok(o.post(f"{T}/jobs/{job_b}/transitions", {"action": "APPROVE"}))
    _start(c, job_b, "1009", t0 + timedelta(hours=9, minutes=1))
    _close(c, job_b, "1011", t0 + timedelta(hours=11))
    a, b = _ok(o.get(f"{T}/jobs/{c.job_id}")), _ok(o.get(f"{T}/jobs/{job_b}"))
    assert (Decimal(a["billable_hours"]), Decimal(b["changeover_carried_hours"])) == (Decimal(6), Decimal(2))
    assert Decimal(b["billable_hours"]) == 4  # 2 carried + 2 own; with the hour of downtime A + B + 1 = 11


def test_in_job_non_revenue_allocation_names_its_approval(api: Api) -> None:
    f = setup_finance(api, "Approval Ref", "REF-1")
    c, o = f.c, f.owner
    _ok(
        o.post(
            f"{T}/policies/REVENUE_RECONCILIATION/versions",
            {
                "scope": "TENANT",
                "values": {"enabled": True, "deduct_non_revenue_from_working_hours": True},
                "reason": "Switched on",
            },
        ),
        201,
    )
    t0 = api.clock.now
    _start(c, c.job_id, "1000", t0)
    move = {
        "client_id": str(uuid.uuid4()),
        "activity_type": "MOBILIZATION",
        "started_at": t0.isoformat(),
        "ended_at": (t0 + timedelta(hours=1)).isoformat(),
        "billable": False,
    }
    activity = _ok(o.post(f"{T}/jobs/{c.job_id}/activities", move), 201)
    _close(c, c.job_id, "1008", t0 + timedelta(hours=8))
    reason = _ok(o.post(f"{T}/revenue-reasons", {"code": "MOVE", "name": "Site move"}), 201)["id"]
    body = {"activity_id": activity["id"], "reason_id": reason, "note": "Moved to the site"}
    proposed = _ok(f.accountant.post(f"{T}/non-revenue-approvals", body), 201)
    _ok(
        f.manager.post(
            f"{T}/non-revenue-approvals/{proposed['id']}/decision", {"decision": "APPROVE", "note": "Checked"}
        )
    )
    run_work_allocations(get_sessionmaker(), api.clock.now)
    [entry] = _allocations(o, kind="AUTHORIZED_ACTIVITY")
    assert entry["activity_type"] == "MOBILIZATION" and Decimal(entry["hours"]) == 1
    assert (entry["approval_ref_type"], entry["approval_ref_ids"]) == ("non_revenue_approval", [proposed["id"]])


def test_field_gets_changeover_jobs_reasons_time_zone_and_policy(api: Api) -> None:
    f = setup_finance(api, "Field Lists", "FLD-1")
    o, sup = f.owner, f.supervisor
    second, contract = _second_customer(f.c, api)
    office_job = _pending_job(f.c, "J-OFFICE", contract)  # created by the office, not requested by the supervisor
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
    assert {"SYNC_CHANGEOVER_JOBS", "SYNC_UNBILLABLE_REASONS"} <= set(boot["capabilities"])
    jobs = {j["id"]: j for j in boot["data"]["changeover_jobs"]}
    assert jobs[office_job]["status"] == "PENDING_APPROVAL" and jobs[office_job]["customer_id"] == second
    assert jobs[office_job]["customer_name"] == "Second Customer" and jobs[office_job]["job_number"] == "J-OFFICE"
    assert office_job not in {j["id"] for j in boot["data"]["jobs"]}  # not on the supervisor's own job list
    assert [r["id"] for r in boot["data"]["unbillable_reasons"]] == [reason["id"]]

    _ok(o.post(f"{T}/jobs/{office_job}/transitions", {"action": "CANCEL", "reason": "Customer withdrew"}))
    body = {"reason": "No longer used", "version": reason["version"]}
    _ok(o.post(f"{T}/engine-hour-reasons/{reason['id']}/deactivate", body))
    changes = _ok(api.client.get("/api/v1/sync/changes", headers=headers, params={"cursor": boot["cursor"]}))
    assert changes["tenant_timezone"] == "Africa/Dar_es_Salaam"
    assert {j["id"]: j["status"] for j in changes["data"]["changeover_jobs"]}[office_job] == "CANCELLED"
    assert [(r["id"], r["is_active"]) for r in changes["data"]["unbillable_reasons"]] == [(reason["id"], False)]

    # The field can read the rules it must follow, and upload a daily report's evidence online.
    assert "changeover_splits_billing" in _ok(sup.get(f"{T}/policies/ENGINE_HOURS/effective"))["values"]
    upload = api.client.post(
        f"{T}/attachments",
        headers=sup.headers(True, None),
        files={"file": ("r.jpg", unique_jpeg(), "image/jpeg")},
        data={"purpose": "DAILY_REPORT_EVIDENCE"},
    )
    assert upload.status_code == 201, upload.text


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
