"""DEC-031 Phase 1 (revenue): the revenue-hour basis (R1), the daily machine sheet (R2) and the hours-to-money
reconciliation (R3) with its explanation by one person and decision by another. Every rule is the tenant policy
REVENUE_RECONCILIATION; switched off (the platform default) nothing changes."""

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import ProgrammingError

from asseta.core.db import get_sessionmaker
from asseta.modules.revenue.reconciliation import run_revenue_reconciliation
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, issue_invoice, setup_finance, tenant_sql
from tests.support.jobs import capture, new_job
from tests.support.notify import drain, member, sql

T = "/api/v1/tenant"
DAY1 = "2026-11-01"  # the clock starts 2026-11-01 09:00 UTC = 12:00 tenant-local (Africa/Dar_es_Salaam)
AFTER_DAY1 = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)  # 10:00 local on 2 Nov: 1 Nov has closed


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _code(r: Any, status: int = 422) -> str:
    assert r.status_code == status, r.text
    return str(r.json()["error"]["code"])


def _policy(o: Actor, **values: Any) -> None:
    _ok(
        o.post(
            f"{T}/policies/REVENUE_RECONCILIATION/versions",
            {"scope": "TENANT", "values": {"enabled": True, **values}, "reason": "Owner switches revenue checks on"},
        ),
        201,
    )


def _run(api: Api, f: FinCtx, job_id: str, opening: str, closing: str, hours: float, mobilization_h: float = 0) -> None:
    """Opening reading -> START -> (movement logged) -> closing reading -> acknowledgement -> COMPLETE."""
    o, t0 = f.owner, api.clock.now
    _ok(o.post(f"{T}/meter-captures", capture(job_id, "OPENING", opening, t0, mode="MANUAL")), 201)
    _ok(o.post(f"{T}/jobs/{job_id}/transitions", {"action": "START"}))
    if mobilization_h:
        body = {
            "client_id": str(uuid.uuid4()),
            "activity_type": "MOBILIZATION",
            "started_at": t0.isoformat(),
            "ended_at": (t0 + timedelta(hours=mobilization_h)).isoformat(),
        }
        assert _ok(o.post(f"{T}/jobs/{job_id}/activities", body), 201)["billable"] is False
    t1 = t0 + timedelta(hours=hours)
    api.clock.set_at(t1)
    _ok(o.post(f"{T}/meter-captures", capture(job_id, "CLOSING", closing, t1, mode="MANUAL")), 201)
    ack = {
        "client_id": str(uuid.uuid4()),
        "method": "NAME_CONFIRMATION",
        "signer_name": "Site",
        "captured_at": t1.isoformat(),
    }
    _ok(o.post(f"{T}/jobs/{job_id}/acknowledgements", ack), 201)
    _ok(o.post(f"{T}/jobs/{job_id}/transitions", {"action": "COMPLETE"}))


def _sweep(at: datetime) -> Any:
    return run_revenue_reconciliation(get_sessionmaker(), at)


def _segments(o: Actor, machine_id: str) -> list[tuple[str, Decimal, str | None]]:
    ledger = _ok(o.get(f"{T}/engine-hours/machines/{machine_id}"))
    return [(s["kind"], Decimal(s["hours"]), s["activity_type"]) for i in ledger["intervals"] for s in i["segments"]]


# --- switched off: today's behaviour ----------------------------------------------------------------------------
def test_switched_off_by_default_nothing_changes(api: Api) -> None:
    f = setup_finance(api, "Revenue Off", "REV-0")
    o, machine = f.owner, f.c.t.machine_id
    _run(api, f, f.c.job_id, "1000", "1008", 8, mobilization_h=1)

    assert Decimal(_ok(o.get(f"{T}/jobs/{f.c.job_id}"))["billable_hours"]) == 8  # movement still billed (today)
    assert _segments(o, machine) == [("CUSTOMER_WORK", Decimal(8), None)]
    totals = _ok(o.get(f"{T}/engine-hours/machines/{machine}"))["totals"]
    assert (Decimal(totals["customer_work_hours"]), Decimal(totals["non_revenue_hours"])) == (Decimal(8), Decimal(0))

    for path in ("daily-machine-sheet", "revenue-differences", "revenue-reasons", "daily-machine-sheet/export.csv"):
        assert _code(o.get(f"{T}/{path}")) == "REVENUE_RECONCILIATION_DISABLED"
    nav = _ok(o.get("/api/v1/me"))["tenants"][0]
    assert "REVENUE_RECONCILIATION" in nav["disabled_capabilities"]
    keys = {m["key"] for m in nav["menus"]}
    assert not keys & {"tenant.engine_hours.daily_sheet", "tenant.revenue_differences", "tenant.revenue_reasons"}

    summary = _sweep(AFTER_DAY1)
    assert (summary.opened, summary.failures) == (0, 0)
    assert sql("SELECT count(*) FROM revenue_difference")[0][0] == 0
    tile = _ok(o.get(f"{T}/accountability/summary"))
    assert tile["revenue_differences"] is None and "revenue_differences" in tile["hidden_tiles"]


# --- R1 ---------------------------------------------------------------------------------------------------------
def test_movement_counts_as_revenue_until_explained_and_approved_by_a_second_person(api: Api) -> None:
    f = setup_finance(api, "Revenue Basis", "REV-B")
    o, acct, mgr, machine = f.owner, f.accountant, f.manager, f.c.t.machine_id
    _policy(o, deduct_non_revenue_from_working_hours=True)  # approval required: the platform default
    _run(api, f, f.c.job_id, "1000", "1008", 8, mobilization_h=1)

    # Logged, not yet explained: still revenue (customer work, billed).
    assert _segments(o, machine) == [("CUSTOMER_WORK", Decimal(8), None)]
    assert Decimal(_ok(o.get(f"{T}/jobs/{f.c.job_id}"))["billable_hours"]) == 8
    [activity] = _ok(o.get(f"{T}/non-revenue-activities", machine_id=machine))["items"]
    assert (activity["activity_type"], Decimal(activity["hours"]), activity["approval_status"]) == (
        "MOBILIZATION",
        Decimal(1),
        "NONE",
    )
    assert activity["job_number"] == "J-001" and activity["machine_code"]
    sheet = _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1))["items"][0]
    assert (Decimal(sheet["non_revenue_pending_hours"]), Decimal(sheet["revenue_hours"])) == (Decimal(1), Decimal(8))

    reason = _ok(o.post(f"{T}/revenue-reasons", {"code": "MOVE", "name": "Moving between sites"}), 201)
    body = {"activity_id": activity["activity_id"], "reason_id": reason["id"], "note": "Drove to the quarry site"}
    proposed = _ok(acct.post(f"{T}/non-revenue-approvals", body), 201)
    assert (proposed["status"], proposed["reason_name"], Decimal(proposed["hours"])) == (
        "PROPOSED",
        "Moving between sites",
        Decimal(1),
    )
    assert _code(mgr.post(f"{T}/non-revenue-approvals", body), 409) == "NON_REVENUE_PENDING"
    url = f"{T}/non-revenue-approvals/{proposed['id']}"
    assert acct.post(f"{url}/decision", {"decision": "APPROVE", "note": "Looks right"}).status_code == 403
    assert Decimal(_ok(o.get(f"{T}/jobs/{f.c.job_id}"))["billable_hours"]) == 8  # proposed is not approved

    drain(api)
    [(link, data)] = sql(
        "SELECT link, data FROM notification WHERE notification_type = 'NON_REVENUE_APPROVAL_REQUESTED' LIMIT 1"
    )
    assert link == f"/tenant/non-revenue-approvals/{proposed['id']}"
    assert (data["kind"], data["record_id"]) == ("NON_REVENUE_APPROVAL", proposed["id"])

    approved = _ok(mgr.post(f"{url}/decision", {"decision": "APPROVE", "note": "Checked the trip log"}))
    assert approved["status"] == "APPROVED" and approved["decided_by_name"] is not None
    assert _ok(o.get(url))["status"] == "APPROVED"
    assert _ok(o.get(f"{T}/non-revenue-approvals", status="APPROVED"))["total"] == 1
    assert _segments(o, machine) == [
        ("CUSTOMER_WORK", Decimal(7), None),
        ("NON_REVENUE", Decimal(1), "MOBILIZATION"),
    ]
    totals = _ok(o.get(f"{T}/engine-hours/machines/{machine}"))["totals"]
    assert [Decimal(totals[k]) for k in ("total_hours", "customer_work_hours", "non_revenue_hours")] == [8, 7, 1]
    assert Decimal(_ok(o.get(f"{T}/jobs/{f.c.job_id}"))["billable_hours"]) == 7  # deducted through billing
    assert _ok(o.get(f"{T}/non-revenue-activities", status="APPROVED"))["total"] == 1

    # Proposer != approver, and a rejection keeps the time as revenue.
    api.clock.set_at(api.clock.now + timedelta(hours=1))
    job2 = new_job(api, f.c, "J-002")
    _run(api, f, job2, "1008", "1012", 4, mobilization_h=1)
    [second] = _ok(o.get(f"{T}/non-revenue-activities", status="NONE"))["items"]
    own = _ok(mgr.post(f"{T}/non-revenue-approvals", {**body, "activity_id": second["activity_id"]}), 201)
    decision = {"decision": "APPROVE", "note": "My own trip"}
    assert _code(mgr.post(f"{T}/non-revenue-approvals/{own['id']}/decision", decision)) == "SEGREGATION_OF_DUTIES"
    rejected = _ok(o.post(f"{T}/non-revenue-approvals/{own['id']}/decision", {**decision, "decision": "REJECT"}))
    assert rejected["status"] == "REJECTED"
    assert Decimal(_ok(o.get(f"{T}/jobs/{job2}"))["billable_hours"]) == 4

    # Configurable: without approval, the declared type is deducted on logging — per billing mode.
    _policy(o, deduct_non_revenue_from_prepaid_hours=True, non_revenue_requires_approval=False)
    api.clock.set_at(api.clock.now + timedelta(hours=1))
    job3 = new_job(api, f.c, "J-003")
    _run(api, f, job3, "1012", "1016", 4, mobilization_h=1)
    assert Decimal(_ok(o.get(f"{T}/jobs/{job3}"))["billable_hours"]) == 4  # an INVOICE job: prepaid-only switch
    assert _code(o.post(f"{T}/non-revenue-approvals", body)) == "NON_REVENUE_APPROVAL_NOT_REQUIRED"


# --- R2 + R3 ----------------------------------------------------------------------------------------------------
def test_daily_sheet_and_reconciliation_open_notify_and_clear_once_money_arrives(api: Api) -> None:
    f = setup_finance(api, "Revenue Co", "REV-1")
    o, machine = f.owner, f.c.t.machine_id
    member(api, f.tid, "manager", "rev-decider")  # holds tenant.revenue.decide (in the notification mirror)
    _policy(
        o,
        deduct_non_revenue_from_working_hours=True,
        non_revenue_requires_approval=False,  # configurable: deducted on logging
        period="DAY",
        case_threshold_amount="100000",
    )
    _run(api, f, f.c.job_id, "1000", "1008", 8, mobilization_h=1)

    page = _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1))
    assert page["total"] == 1
    row = page["items"][0]
    assert (row["machine_id"], row["day"], row["reading_count"]) == (machine, DAY1, 2)
    assert row["machine_code"] and row["machine_name"]
    assert [Decimal(row[k]) for k in ("first_reading", "last_reading")] == [1000, 1008]
    hours = ("engine_hours", "customer_work_hours", "non_revenue_hours", "revenue_hours", "unexplained_hours")
    assert [Decimal(row[k]) for k in hours] == [8, 7, 1, 7, 0]
    assert {k: Decimal(v) for k, v in row["non_revenue_by_type"].items()} == {"MOBILIZATION": 1}
    [job] = row["jobs"]
    assert (job["job_id"], job["job_number"], job["customer_name"]) == (f.c.job_id, "J-001", "Road Builders Ltd")
    [money] = row["money"]
    assert money["currency"] == "TZS"
    assert [Decimal(money[k]) for k in ("expected", "in_progress", "attributed", "difference")] == [
        595000,
        0,
        0,
        595000,
    ]

    # Filters: machine, site, day range.
    assert (
        _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1, machine_id=str(uuid.uuid4())))["total"] == 0
    )
    assert _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1, site_id=str(uuid.uuid4())))["total"] == 0
    assert _ok(o.get(f"{T}/daily-machine-sheet", day_from="2026-11-02", day_to="2026-11-03"))["total"] == 0
    assert _code(o.get(f"{T}/daily-machine-sheet", day_from="2026-01-01", day_to=DAY1)) == "RANGE_TOO_LONG"

    detail = _ok(o.get(f"{T}/daily-machine-sheet/{machine}/{DAY1}"))
    assert [r["kind"] for r in detail["readings"]] == ["OPENING", "CLOSING"]
    assert all(r["job_number"] == "J-001" for r in detail["readings"])
    [segment] = detail["segments"]
    assert (segment["kind"], Decimal(segment["customer_work_hours_in_day"])) == ("CUSTOMER_WORK", Decimal(7))
    assert detail["money_sources"] == []

    exported = o.get(f"{T}/daily-machine-sheet/export.csv", day_from=DAY1, day_to=DAY1)
    assert exported.status_code == 200 and exported.headers["content-type"].startswith("text/csv")
    [line] = list(csv.DictReader(io.StringIO(exported.text)))
    assert (line["jobs"], line["customers"], Decimal(line["TZS_difference"])) == (
        "J-001",
        "Road Builders Ltd",
        Decimal(595000),
    )
    assert Decimal(line["non_revenue_mobilization_hours"]) == 1

    # The day closed: completed work not matched by money is a difference to explain (once, however often it runs).
    first, again = _sweep(AFTER_DAY1), _sweep(AFTER_DAY1 + timedelta(hours=1))
    assert (first.opened, again.opened, first.failures) == (1, 0, 0)
    [diff] = _ok(o.get(f"{T}/revenue-differences"))["items"]
    assert (diff["status"], diff["period_kind"], diff["period_key"]) == ("OPEN", "DAY", f"DAY:{DAY1}")
    assert (diff["local_from"], diff["local_to"], diff["machine_code"]) == (DAY1, DAY1, row["machine_code"])
    assert [Decimal(diff[k]) for k in ("expected_amount", "attributed_amount", "difference")] == [595000, 0, 595000]
    assert [Decimal(diff[k]) for k in ("customer_work_hours", "non_revenue_hours")] == [7, 1]
    assert diff["detail"]["jobs"][0]["job_number"] == "J-001"
    assert diff["case_id"] and diff["case_number"].startswith("CASE-")  # above the case threshold
    assert _ok(o.get(f"{T}/revenue-differences/{diff['id']}"))["id"] == diff["id"]
    assert _ok(o.get(f"{T}/revenue-differences", status="CLEARED"))["total"] == 0

    drain(api)
    rows = sql(
        "SELECT link, entity_type, entity_id, data FROM notification WHERE notification_type = 'REVENUE_DIFFERENCE'"
    )
    assert rows, "no REVENUE_DIFFERENCE notification"
    link, entity, entity_id, data = rows[0]
    assert (link, entity, entity_id) == (f"/tenant/revenue-differences/{diff['id']}", "revenue_difference", diff["id"])
    assert (data["kind"], data["record_id"]) == ("REVENUE_DIFFERENCE", diff["id"])

    api.clock.set_at(AFTER_DAY1)
    tile = _ok(o.get(f"{T}/accountability/summary"))["revenue_differences"]
    assert (tile["open"], tile["awaiting_decision"], tile["items"][0]["id"]) == (1, 0, diff["id"])
    assert tile["amounts"] == [{"currency": "TZS", "count": 1, "amount": "595000.0000"}]
    flags = _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1))["items"][0]["flags"]
    assert "REVENUE_DIFFERENCE" in flags

    # The invoice is issued later: the money is attributed to the day and the next check clears the difference.
    issue_invoice(f, [f.c.job_id])
    money = _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1))["items"][0]["money"][0]
    assert (Decimal(money["attributed"]), Decimal(money["difference"])) == (Decimal(595000), Decimal(0))
    sources = _ok(o.get(f"{T}/daily-machine-sheet/{machine}/{DAY1}"))["money_sources"]
    assert {s["source"] for s in sources} == {"INVOICE_LINE"} and sources[0]["job_number"] == "J-001"
    assert _sweep(AFTER_DAY1 + timedelta(hours=2)).cleared == 1
    cleared = _ok(o.get(f"{T}/revenue-differences/{diff['id']}"))
    assert (cleared["status"], Decimal(cleared["difference"])) == ("CLEARED", Decimal(0))
    assert _sweep(AFTER_DAY1 + timedelta(hours=3)).opened == 0


def test_explanation_by_one_person_decision_by_another(api: Api) -> None:
    f = setup_finance(api, "Revenue Explain", "REV-2")
    o, mgr, acct = f.owner, f.manager, f.accountant
    _policy(o, period="DAY")
    _run(api, f, f.c.job_id, "1000", "1008", 8)
    assert _sweep(AFTER_DAY1).opened == 1
    [diff] = _ok(o.get(f"{T}/revenue-differences"))["items"]
    url = f"{T}/revenue-differences/{diff['id']}"
    assert Decimal(diff["expected_amount"]) == 680000 and diff["case_id"] is None  # no case threshold configured

    # Tenant reason list (full lifecycle; managed by decide holders).
    assert acct.post(f"{T}/revenue-reasons", {"code": "X", "name": "Nope"}).status_code == 403
    reason = _ok(o.post(f"{T}/revenue-reasons", {"code": "LATE", "name": "Invoice issued late"}), 201)
    assert _code(o.post(f"{T}/revenue-reasons", {"code": "LATE", "name": "Again"}), 409) == "DUPLICATE_REASON"
    reason = _ok(o.put(f"{T}/revenue-reasons/{reason['id']}", {"code": "LATE", "name": "Invoice late", "version": 1}))
    assert _ok(acct.get(f"{T}/revenue-reasons/{reason['id']}"))["name"] == "Invoice late"
    _ok(o.post(f"{T}/revenue-reasons/{reason['id']}/deactivate", {"reason": "Testing the list"}))
    assert _ok(acct.get(f"{T}/revenue-reasons"))["total"] == 0
    assert _ok(acct.get(f"{T}/revenue-reasons", include_inactive=True))["total"] == 1
    explanation = {"reason_id": reason["id"], "note": "Invoice goes out on Monday"}
    assert _code(acct.post(f"{url}/explanation", explanation)) == "REASON_INACTIVE"
    _ok(o.post(f"{T}/revenue-reasons/{reason['id']}/reactivate", {"reason": "Back in use"}))

    # Permissions by role template: the field supervisor sees nothing; the accountant explains but never decides.
    assert f.supervisor.get(f"{T}/revenue-differences").status_code == 403
    proposed = _ok(acct.post(f"{url}/explanation", explanation))
    assert (proposed["status"], proposed["reason_name"]) == ("EXPLANATION_PROPOSED", "Invoice late")
    assert proposed["explained_by_name"] is not None and proposed["explanation_note"] == explanation["note"]
    assert acct.post(f"{url}/decision", {"decision": "APPROVE", "note": "Fine by me"}).status_code == 403
    assert _code(mgr.post(f"{url}/explanation", explanation), 409) == "REVENUE_DIFFERENCE_NOT_OPEN"

    rejected = _ok(mgr.post(f"{url}/decision", {"decision": "REJECT", "note": "Not the reason, check again"}))
    assert (rejected["status"], rejected["reason_id"], rejected["explained_by"]) == ("OPEN", None, None)
    _ok(mgr.post(f"{url}/explanation", explanation))
    approve = {"decision": "APPROVE", "note": "Checked the invoice book"}
    assert _code(mgr.post(f"{url}/decision", approve)) == "SEGREGATION_OF_DUTIES"
    approved = _ok(o.post(f"{url}/decision", approve))
    assert (approved["status"], approved["decision_note"]) == ("EXPLAINED", approve["note"])
    assert approved["decided_by_name"] is not None
    assert _code(o.post(f"{url}/decision", approve), 409) == "REVENUE_DIFFERENCE_STATE"
    assert _code(acct.post(f"{url}/explanation", explanation), 409) == "REVENUE_DIFFERENCE_NOT_OPEN"
    with pytest.raises(ProgrammingError):  # a decided difference is final in the database too
        tenant_sql(f.tid, "UPDATE revenue_difference SET status = 'OPEN' WHERE id = :i", i=diff["id"])
    assert _sweep(AFTER_DAY1 + timedelta(hours=1)).refreshed == 0  # final: never recomputed

    # Next day's work: confirmed as a real difference (money to recover) without an explanation.
    api.clock.set_at(datetime(2026, 11, 2, 6, 0, tzinfo=UTC))
    job2 = new_job(api, f.c, "J-002")
    _run(api, f, job2, "1008", "1012", 4)
    assert _sweep(datetime(2026, 11, 3, 6, 0, tzinfo=UTC)).opened == 1
    second = _ok(o.get(f"{T}/revenue-differences", status="OPEN"))["items"][0]
    assert second["period_key"] == "DAY:2026-11-02"
    confirmed = _ok(
        mgr.post(
            f"{T}/revenue-differences/{second['id']}/decision", {"decision": "CONFIRM", "note": "Customer to be chased"}
        )
    )
    assert confirmed["status"] == "CONFIRMED"
    days = _ok(o.get(f"{T}/revenue-differences", day_from="2026-11-02", day_to="2026-11-02"))
    assert [d["id"] for d in days["items"]] == [second["id"]]


def test_job_period_reconciles_each_completed_job(api: Api) -> None:
    f = setup_finance(api, "Revenue Jobs", "REV-3")
    o = f.owner
    _policy(o, period="JOB", tolerance_percent="0")
    _run(api, f, f.c.job_id, "1000", "1004", 4)
    assert _sweep(api.clock.now).opened == 1  # the job's period closes when it completes
    [diff] = _ok(o.get(f"{T}/revenue-differences"))["items"]
    assert (diff["period_kind"], diff["period_key"]) == ("JOB", f"JOB:{f.c.job_id}")
    assert (diff["job_id"], diff["job_number"]) == (f.c.job_id, "J-001")
    issue_invoice(f, [f.c.job_id])
    assert _sweep(api.clock.now + timedelta(minutes=5)).cleared == 1


def test_another_tenant_never_sees_revenue_records(api: Api) -> None:
    f = setup_finance(api, "Revenue Own", "REV-4")
    _policy(f.owner, period="DAY")
    _run(api, f, f.c.job_id, "1000", "1008", 8)
    _sweep(AFTER_DAY1)
    [diff] = _ok(f.owner.get(f"{T}/revenue-differences"))["items"]
    t = api.onboard("Revenue Other", price="1000")
    api.activate(t)
    other: Actor = t["owner"]
    _policy(other, period="DAY")
    assert _ok(other.get(f"{T}/revenue-differences"))["total"] == 0
    assert other.get(f"{T}/revenue-differences/{diff['id']}").status_code == 404
    body = {"reason_id": str(uuid.uuid4()), "note": "Not mine at all"}
    assert other.post(f"{T}/revenue-differences/{diff['id']}/explanation", body).status_code == 404
    assert other.get(f"{T}/daily-machine-sheet/{f.c.t.machine_id}/{DAY1}").status_code == 404


def _daily(o: Actor, api: Api, machine: str, reading: str, at: datetime) -> None:
    body = capture("", "DAILY", reading, at, mode="MANUAL")
    body.pop("job_id")
    body["machine_id"] = machine
    if at > api.clock.now:
        api.clock.set_at(at)
    _ok(o.post(f"{T}/meter-captures", body), 201)


def _baseline(api: Api, f: FinCtx, machine: str) -> Actor:
    """Engine-hour reconciliation starts at an approved baseline (the earliest reading, approved by a second owner)."""
    approver = member(api, f.tid, "owner", f"rev-approver-{machine[:8]}")
    base = _ok(f.owner.post(f"{T}/meter-baselines/from-reading", {"machine_id": machine}), 201)
    _ok(approver.post(f"{T}/meter-baselines/{base['id']}/decision", {"decision": "APPROVE", "note": "Checked it"}))
    return approver


def _classify(api: Api, f: FinCtx, machine: str) -> None:
    """The unallocated segment is explained as non-customer activity and approved by a second person."""
    o = f.owner
    approver = _baseline(api, f, machine)
    seg = next(
        i
        for i in _ok(o.get(f"{T}/engine-hours/machines/{machine}"))["intervals"]
        if i["segments"][0]["kind"] == "UNALLOCATED"
    )
    reason = _ok(
        o.post(f"{T}/engine-hour-reasons", {"kind": "NON_CUSTOMER_CATEGORY", "code": "YARD", "name": "Yard move"}), 201
    )
    proposed = _ok(
        o.post(
            f"{T}/engine-hours/classifications",
            {
                "machine_id": machine,
                "start_ref": seg["start"]["ref"],
                "end_ref": seg["end"]["ref"],
                "outcome": "APPROVED_NON_CUSTOMER",
                "reason_id": reason["id"],
                "note": "Moved back to the yard",
            },
        ),
        201,
    )
    decision = {"decision": "APPROVE", "note": "Yard log checked"}
    _ok(approver.post(f"{T}/engine-hours/classifications/{proposed['id']}/decision", decision))


def test_unexplained_hours_outside_jobs_are_expected_revenue_until_approved(api: Api) -> None:
    f = setup_finance(api, "Revenue Idle", "REV-6")
    o, machine = f.owner, f.c.t.machine_id
    _policy(o, period="DAY")
    _run(api, f, f.c.job_id, "1000", "1008", 8)
    issue_invoice(f, [f.c.job_id])  # the job's money is in: only the unexplained hours remain
    _daily(o, api, machine, "1010", api.clock.now + timedelta(hours=3))  # 2 h after the job, same local day

    def money() -> dict[str, Any]:
        row = _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1))["items"][0]
        assert Decimal(row["unexplained_hours"]) == 2
        return dict(row["money"][0])

    m = money()
    assert [Decimal(m[k]) for k in ("unexplained_hours", "unexplained_expected", "expected", "difference")] == [
        2,
        170000,  # the machine category's rate card (85,000/h)
        850000,
        170000,
    ]
    _policy(o, period="DAY", unexplained_hours_treatment="EXCLUDE")
    m = money()
    assert [Decimal(m[k]) for k in ("unexplained_hours", "unexplained_expected", "difference")] == [2, 0, 0]
    _policy(o, period="DAY", unexplained_hours_rate_source="TENANT_RATE", unexplained_hours_rate="1000")
    assert Decimal(money()["unexplained_expected"]) == 2000
    _policy(o, period="DAY", unexplained_hours_rate_source="MACHINE_RATE_CARD")

    assert _sweep(AFTER_DAY1).opened == 1
    [diff] = _ok(o.get(f"{T}/revenue-differences"))["items"]
    assert [Decimal(diff[k]) for k in ("unexplained_hours", "unexplained_expected_amount", "difference")] == [
        2,
        170000,
        170000,
    ]
    unexplained = diff["detail"]["unexplained"]
    assert (Decimal(unexplained["hours"]), Decimal(unexplained["expected"])) == (Decimal(2), Decimal(170000))
    confirmed = _ok(
        f.manager.post(
            f"{T}/revenue-differences/{diff['id']}/decision", {"decision": "CONFIRM", "note": "Idle hours unexplained"}
        )
    )
    assert confirmed["status"] == "CONFIRMED" and confirmed["adjustments"] == []

    # Approved later as non-customer activity: the decided difference is not rewritten, it gets an adjustment.
    _classify(api, f, machine)
    after = _ok(o.get(f"{T}/revenue-differences/{diff['id']}"))
    assert (after["status"], Decimal(after["difference"])) == ("CONFIRMED", Decimal(170000))
    [adj] = after["adjustments"]
    assert (adj["cause_type"], Decimal(adj["amount"]), Decimal(adj["new_difference"])) == (
        "engine_hour_classification",
        Decimal(-170000),
        Decimal(0),
    )
    assert Decimal(after["adjusted_difference"]) == 0 and adj["created_by_name"] is not None
    row = _ok(o.get(f"{T}/daily-machine-sheet", day_from=DAY1, day_to=DAY1))["items"][0]
    assert (Decimal(row["unexplained_hours"]), Decimal(row["approved_non_customer_hours"])) == (Decimal(0), Decimal(2))
    assert Decimal(row["money"][0]["difference"]) == 0


def test_an_open_difference_is_recomputed_when_the_hours_are_approved(api: Api) -> None:
    f = setup_finance(api, "Revenue Recompute", "REV-7")
    o, machine = f.owner, f.c.t.machine_id
    _policy(o, period="DAY", recheck_days=1)
    _run(api, f, f.c.job_id, "1000", "1008", 8)
    issue_invoice(f, [f.c.job_id])
    _daily(o, api, machine, "1010", api.clock.now + timedelta(hours=3))
    assert _sweep(AFTER_DAY1).opened == 1
    [diff] = _ok(o.get(f"{T}/revenue-differences"))["items"]
    api.clock.set_at(AFTER_DAY1 + timedelta(days=5))  # beyond the re-check window: only the approval recomputes it
    _classify(api, f, machine)
    after = _ok(o.get(f"{T}/revenue-differences/{diff['id']}"))
    assert (after["status"], Decimal(after["difference"]), after["adjustments"]) == ("CLEARED", Decimal(0), [])
