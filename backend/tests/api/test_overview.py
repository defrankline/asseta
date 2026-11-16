"""Gate 7 tenant overview: sections gated by their own permission (omitted otherwise), KPI values from the modules'
own rules (receivables, custody, fleet map status), per-section freshness, and tenant isolation."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from tests.support.api import Api
from tests.support.finance import FinCtx, category, expense_policy, role, setup_finance
from tests.support.hours import RATE
from tests.support.machine_reports import ReportCtx, idle, later, report_body, setup_reports, submit

OVERVIEW = "/api/v1/tenant/overview"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _money(body: dict[str, Any], currency: str = "TZS") -> dict[str, Any]:
    return next(c for c in body["money"]["currencies"] if c["currency"] == currency)


def _report(api: Api, ctx: ReportCtx) -> str:
    """A machine report (2 non-productive hours) waiting for its decision."""
    body = report_body(ctx.machine_id, "1002.0", later(api, 2), [idle(ctx.reasons["IDLE_ON_SITE"], 2)])
    return str(submit(ctx.f.supervisor, body)["id"])


def _setup_money(api: Api, f: FinCtx) -> dict[str, Any]:
    """A credit sale invoicing 340,000 (4 h x 85,000), 200,000 of it paid by bank and verified, a 100,000 float and a
    30,000 approved cash expense, all in November 2026 (tenant-local)."""
    sale = {
        "customer_id": f.customer_id,
        "machine_id": f.c.t.machine_id,
        "hours": "4",
        "client_id": str(uuid.uuid4()),
        "payments": [{"amount": str(4 * RATE), "method": "CREDIT"}],
    }
    inv = _ok(f.accountant.post("/api/v1/tenant/hours-purchases", sale), 201)["credit_invoice"]
    paid = _ok(
        f.accountant.post(
            f"/api/v1/tenant/credit-invoices/{inv['id']}/payments",
            {
                "amount": "200000",
                "method": "BANK",
                "reference": "BNK-1",
                "received_at": api.clock.now.isoformat(),
                "client_id": str(uuid.uuid4()),
            },
        ),
        201,
    )
    payment_id = paid["payments"][0]["payment_id"]
    _ok(f.accountant2.post(f"/api/v1/tenant/customer-payments/{payment_id}/decision", {"verified": True}))
    _ok(f.accountant.post("/api/v1/tenant/cash/floats", {"staff_member_id": f.sup_staff_id, "amount": "100000"}), 201)
    misc = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="50000")
    spent = _ok(
        f.supervisor.post(
            "/api/v1/tenant/expenses",
            {
                "category_id": misc,
                "description": "hydraulic hose",
                "amount": "30000",
                "incurred_at": api.clock.now.isoformat(),
                "machine_id": f.c.t.machine_id,
                "paid_from": "CASH_CUSTODY",
            },
        ),
        201,
    )
    assert spent["status"] == "APPROVED"
    return dict(inv)


def test_owner_sees_every_section_with_values_and_freshness(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    before = _ok(f.owner.get(OVERVIEW))
    assert before["timezone"] == "Africa/Dar_es_Salaam" and before["tenant_id"] == f.tid
    fleet = before["fleet"]
    assert fleet["machines"] == 1 and sum(fleet["connectivity"].values()) == 1
    assert fleet["reported_work_state"]["NOT_REPORTED"] == 1 and fleet["engine_on_verified"] == 0
    assert before["work"]["machine_reports_by_status"] == {"SUBMITTED": 0, "APPROVED": 0, "REJECTED": 0}
    assert (before["work"]["pending_approvals"], before["work"]["open_exceptions"]) == (0, 0)
    assert before["money"]["currencies"] == [] and before["money"]["latest_source_at"] is None
    zero = {"info": 0, "warning": 0, "critical": 0}
    assert before["risk"] == {"open_cases": zero, "signals_last_7_days": zero, "latest_source_at": None}

    inv = _setup_money(api, f)
    _report(api, ctx)
    body = _ok(f.owner.get(OVERVIEW))
    tzs = _money(body)
    assert Decimal(tzs["receivables_outstanding"]) == Decimal(inv["amount"]) - 200000 == Decimal("140000")
    assert Decimal(tzs["receivables_overdue"]) == 0 and tzs["overdue_invoices"] == 0
    # The dashboard's overdue link opens the credit invoice list with the same definition.
    assert f.owner.get("/api/v1/tenant/credit-invoices", overdue="true").json()["total"] == 0
    assert Decimal(tzs["verified_receipts_mtd"]) == 200000
    assert Decimal(tzs["approved_expenses_mtd"]) == 30000
    assert Decimal(tzs["cash_with_supervisors"]) == 70000  # float 100,000 - approved cash spend 30,000
    assert body["money"]["month_start"] == "2026-11-01"
    assert body["money"]["latest_source_at"] is not None
    assert body["work"]["machine_reports_by_status"]["SUBMITTED"] == 1
    assert body["fleet"]["reported_work_state"]["REPORT_PENDING"] == 1
    assert body["as_of"] >= body["money"]["latest_source_at"]

    # Past the due date the same balance is overdue; a new month resets the month-to-date figures.
    api.clock.set_at(api.clock.now + timedelta(days=45))
    past_due = _money(_ok(f.owner.get(OVERVIEW)))
    assert Decimal(past_due["receivables_overdue"]) == Decimal("140000") and past_due["overdue_invoices"] == 1
    overdue = f.owner.get("/api/v1/tenant/credit-invoices", overdue="true").json()
    assert [i["id"] for i in overdue["items"]] == [inv["id"]] and overdue["total"] == past_due["overdue_invoices"]
    assert Decimal(past_due["verified_receipts_mtd"]) == 0 and Decimal(past_due["approved_expenses_mtd"]) == 0
    assert Decimal(past_due["cash_with_supervisors"]) == 70000


def test_sections_follow_permissions(api: Api) -> None:
    f = setup_finance(api)
    # finance + machine report read + case/signal read, no fleet/meter/approval read
    acct = _ok(f.accountant.get(OVERVIEW))
    assert acct["fleet"] is None and acct["money"] is not None and acct["risk"] is not None
    assert acct["work"]["machine_reports_by_status"]["SUBMITTED"] == 0
    assert acct["work"]["pending_approvals"] is None and acct["work"]["readings_needing_review"] is None
    sup = _ok(f.supervisor.get(OVERVIEW))  # fleet + machine report + meter read; no finance, cases or signals
    assert sup["fleet"] is not None and sup["work"]["open_exceptions"] == 0
    assert sup["money"] is None and sup["risk"] is None and sup["work"]["pending_approvals"] is None
    mgr = _ok(f.manager.get(OVERVIEW))
    assert mgr["money"] is None and mgr["work"]["pending_approvals"] == 0 and mgr["risk"]["open_cases"] is not None
    operator = role(api, f.tid, "operator", "op-1")
    denied = operator.get(OVERVIEW)
    assert denied.status_code == 403 and "tenant.fleet.read" in denied.json()["error"]["message"]


def test_overview_is_tenant_isolated(api: Api) -> None:
    f = setup_finance(api)
    _setup_money(api, f)
    other = api.onboard("Other Hire", price="1")
    api.activate(other)
    body = _ok(other["owner"].get(OVERVIEW))
    assert body["tenant_id"] == other["tenant"]["id"]
    assert body["fleet"]["machines"] == 0 and body["fleet"]["latest_source_at"] is None
    assert body["money"]["currencies"] == [] and sum(body["work"]["machine_reports_by_status"].values()) == 0
    crossed = other["owner"].get(OVERVIEW, tenant=f.tid)  # another tenant's id in X-Tenant-ID
    assert crossed.status_code == 403 and crossed.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
