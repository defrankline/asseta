"""Gate 7 tenant overview: sections gated by their own permission (omitted otherwise), KPI values from the modules'
own rules (receivables, custody, fleet map status), per-section freshness, and tenant isolation."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from tests.support.api import Api
from tests.support.finance import FinCtx, category, complete_job, expense_policy, issue_invoice, role, setup_finance

OVERVIEW = "/api/v1/tenant/overview"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _money(body: dict[str, Any], currency: str = "TZS") -> dict[str, Any]:
    return next(c for c in body["money"]["currencies"] if c["currency"] == currency)


def _setup_money(api: Api, f: FinCtx) -> dict[str, Any]:
    """Issued invoice 552,500 (6.5 h x 85,000), 200,000 of it paid and verified, a 100,000 float and a 30,000
    approved cash expense, all in November 2026 (tenant-local)."""
    complete_job(api, f, f.c.job_id, "1000.0", "1008.0", 9, downtime_h=1.5)
    inv = issue_invoice(f, [f.c.job_id])
    pay = _ok(
        f.accountant.post(
            "/api/v1/tenant/customer-payments",
            {
                "customer_id": f.customer_id,
                "amount": "200000",
                "method": "BANK",
                "reference": "BNK-1",
                "received_at": api.clock.now.isoformat(),
                "allocations": [{"invoice_id": inv["id"], "amount": "200000"}],
            },
        ),
        201,
    )
    _ok(f.accountant2.post(f"/api/v1/tenant/customer-payments/{pay['id']}/decision", {"verified": True}))
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
    f = setup_finance(api)
    before = _ok(f.owner.get(OVERVIEW))
    assert before["timezone"] == "Africa/Dar_es_Salaam" and before["tenant_id"] == f.tid
    fleet = before["fleet"]
    assert fleet["machines"] == 1 and sum(fleet["connectivity"].values()) == 1
    assert fleet["reported_work_state"]["NO_ACTIVE_JOB"] == 1 and fleet["engine_on_verified"] == 0
    assert before["work"]["jobs_by_status"]["APPROVED"] == 1
    assert (before["work"]["pending_approvals"], before["work"]["open_exceptions"]) == (0, 0)
    assert before["money"]["currencies"] == [] and before["money"]["latest_source_at"] is None
    zero = {"info": 0, "warning": 0, "critical": 0}
    assert before["risk"] == {"open_cases": zero, "signals_last_7_days": zero, "latest_source_at": None}

    inv = _setup_money(api, f)
    body = _ok(f.owner.get(OVERVIEW))
    tzs = _money(body)
    assert Decimal(tzs["receivables_outstanding"]) == Decimal(inv["total"]) - 200000 == Decimal("352500")
    assert Decimal(tzs["receivables_overdue"]) == 0 and tzs["overdue_invoices"] == 0
    assert Decimal(tzs["verified_receipts_mtd"]) == 200000
    assert Decimal(tzs["approved_expenses_mtd"]) == 30000
    assert Decimal(tzs["cash_with_supervisors"]) == 70000  # float 100,000 - approved cash spend 30,000
    assert body["money"]["month_start"] == "2026-11-01"
    assert body["money"]["latest_source_at"] is not None
    assert body["work"]["jobs_by_status"]["COMPLETED"] == 1
    assert body["as_of"] >= body["money"]["latest_source_at"]

    # Past the due date the same balance is overdue; a new month resets the month-to-date figures.
    api.clock.set_at(api.clock.now + timedelta(days=45))
    later = _money(_ok(f.owner.get(OVERVIEW)))
    assert Decimal(later["receivables_overdue"]) == Decimal("352500") and later["overdue_invoices"] == 1
    assert Decimal(later["verified_receipts_mtd"]) == 0 and Decimal(later["approved_expenses_mtd"]) == 0
    assert Decimal(later["cash_with_supervisors"]) == 70000


def test_sections_follow_permissions(api: Api) -> None:
    f = setup_finance(api)
    acct = _ok(f.accountant.get(OVERVIEW))  # finance + job read + case/signal read, no fleet/meter/approval read
    assert acct["fleet"] is None and acct["money"] is not None and acct["risk"] is not None
    assert acct["work"]["jobs_by_status"]["APPROVED"] == 1
    assert acct["work"]["pending_approvals"] is None and acct["work"]["readings_needing_review"] is None
    sup = _ok(f.supervisor.get(OVERVIEW))  # fleet + job + meter read; no finance, cases or signals
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
    assert body["money"]["currencies"] == [] and sum(body["work"]["jobs_by_status"].values()) == 0
    crossed = other["owner"].get(OVERVIEW, tenant=f.tid)  # another tenant's id in X-Tenant-ID
    assert crossed.status_code == 403 and crossed.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
