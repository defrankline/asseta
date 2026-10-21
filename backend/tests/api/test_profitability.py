"""Gate 5 (R1-G): profitability by machine / job / customer / period from recognized revenue (issued invoice lines
excl. tax, net of reversals) minus categorized direct costs (approved expenses + attributed fuel); per currency."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from tests.support.api import Api
from tests.support.finance import FinCtx, category, complete_job, expense_policy, issue_invoice, setup_finance
from tests.support.jobs import unique_jpeg

PROFIT = "/api/v1/tenant/finance/profitability"


def _rows(f: FinCtx, group_by: str, first: str, last: str) -> dict[tuple[str, str], dict[str, Any]]:
    r = f.accountant.get(PROFIT, group_by=group_by, **{"from": first, "to": last})
    assert r.status_code == 200, r.text
    return {(row["label"], row["currency"]): row for row in r.json()["rows"]}


def _money(row: dict[str, Any], *keys: str) -> tuple[Decimal, ...]:
    return tuple(Decimal(row[k]) for k in keys)


def test_profitability_by_machine_job_customer_and_period(api: Api) -> None:
    f = setup_finance(api)
    repair, fuel = category(f, "REPAIR", "Repairs"), category(f, "FUEL", "Fuel")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="50000")
    complete_job(api, f, f.c.job_id, "1000.0", "1008.0", 9, downtime_h=1.5)
    inv = issue_invoice(f, [f.c.job_id])  # 552,500 TZS, issued 2026-11-01 (local)
    at = datetime.fromisoformat("2026-11-01T12:00:00+00:00").isoformat()

    def expense(cat: str, amount: str, **kw: Any) -> dict[str, Any]:
        body = {
            "category_id": cat,
            "description": "cost",
            "amount": amount,
            "incurred_at": at,
            "paid_from": "COMPANY",
            **kw,
        }
        r = f.owner.post("/api/v1/tenant/expenses", body)
        assert r.status_code == 201, r.text
        out: dict[str, Any] = r.json()
        return out

    def decide(e: dict[str, Any], approve: bool) -> None:
        r = f.manager.post(f"/api/v1/tenant/approvals/{e['approval_request_id']}/decision", {"approve": approve})
        assert r.status_code == 200, r.text

    expense(repair, "30000", job_id=f.c.job_id)  # auto-approved, job + machine
    expense(repair, "45000", machine_id=f.c.t.machine_id)  # auto-approved, machine only
    expense(repair, "70000", job_id=f.c.job_id)  # pending: never counts
    decide(expense(repair, "60000", job_id=f.c.job_id), False)  # rejected: never counts
    receipt = api.client.post(
        "/api/v1/tenant/expense-receipts",
        headers=f.owner.headers(True, None),
        files={"file": ("r.jpg", unique_jpeg(), "image/jpeg")},
    ).json()["id"]
    usd = expense(repair, "10", machine_id=f.c.t.machine_id, currency="USD", receipt_attachment_ids=[receipt])
    decide(usd, True)  # separate currency row
    bulk = expense(fuel, "3000000")
    decide(bulk, True)
    fe = "/api/v1/tenant/fuel-events"
    for body in (
        {"event_type": "PURCHASE", "litres": "1000", "unit_price": "3000", "expense_id": bulk["id"]},  # to stock
        {"event_type": "ISSUE", "litres": "20", "unit_price": "3000", "job_id": f.c.job_id},  # 60,000
        {"event_type": "PURCHASE", "litres": "10", "unit_price": "3100", "machine_id": f.c.t.machine_id},  # 31,000
        {"event_type": "USAGE", "litres": "15", "machine_id": f.c.t.machine_id},
    ):
        assert f.supervisor.post(fe, {**body, "occurred_at": at}).status_code == 201

    machine = _rows(f, "MACHINE", "2026-11-01", "2026-11-01")
    [(label, _)] = [k for k in machine if k[1] == "TZS"]
    m = machine[(label, "TZS")]
    assert _money(m, "revenue", "reversed_revenue", "net_revenue") == (Decimal(552500), Decimal(0), Decimal(552500))
    assert _money(m, "expense_cost", "fuel_cost", "direct_cost", "margin") == (
        Decimal(75000),
        Decimal(91000),
        Decimal(166000),
        Decimal(386500),
    )
    assert {k: Decimal(v) for k, v in m["cost_by_category"].items()} == {"FUEL": 91000, "REPAIR": 75000}
    usd = machine[(label, "USD")]
    assert _money(usd, "net_revenue", "expense_cost", "margin") == (
        Decimal(0),
        Decimal(10),
        Decimal(-10),
    )  # never mixed

    job = _rows(f, "JOB", "2026-11-01", "2026-11-01")
    assert _money(job[("J-001", "TZS")], "net_revenue", "expense_cost", "fuel_cost", "margin") == (
        Decimal(552500),
        Decimal(30000),
        Decimal(60000),
        Decimal(462500),
    )
    assert _money(job[("Unattributed", "TZS")], "expense_cost", "fuel_cost", "margin") == (
        Decimal(45000),
        Decimal(31000),
        Decimal(-76000),
    )
    customer = _rows(f, "CUSTOMER", "2026-11-01", "2026-11-01")
    assert _money(customer[("Road Builders Ltd", "TZS")], "net_revenue", "direct_cost", "margin") == (
        Decimal(552500),
        Decimal(90000),
        Decimal(462500),
    )

    # Reversal recognized in the period it happens; the original period is not rewritten.
    api.clock.set_at(api.clock.now + timedelta(hours=16))  # 2026-11-02 10:00 UTC
    voided = f.accountant.post(f"/api/v1/tenant/hire-invoices/{inv['id']}/void", {"reason": "Disputed hours"})
    assert voided.status_code == 200, voided.text
    day2 = _rows(f, "CUSTOMER", "2026-11-02", "2026-11-02")[("Road Builders Ltd", "TZS")]
    assert _money(day2, "revenue", "reversed_revenue", "net_revenue") == (Decimal(0), Decimal(552500), Decimal(-552500))
    both = _rows(f, "CUSTOMER", "2026-11-01", "2026-11-02")[("Road Builders Ltd", "TZS")]
    assert _money(both, "net_revenue", "margin") == (Decimal(0), Decimal(-90000))
    assert _money(_rows(f, "CUSTOMER", "2026-11-01", "2026-11-01")[("Road Builders Ltd", "TZS")], "net_revenue") == (
        Decimal(552500),
    )
    assert f.supervisor.get(PROFIT, group_by="JOB", **{"from": "2026-11-01", "to": "2026-11-01"}).status_code == 403
