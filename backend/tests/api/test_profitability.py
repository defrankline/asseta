"""Gate 5 (R1-G), ADR-008: profitability by machine / customer / period from recognized revenue (customer hours used
in approved machine reports x their order's price, dated at approval) minus categorized direct costs (approved
expenses + attributed fuel, per machine); per currency."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from tests.support.api import Api
from tests.support.finance import FinCtx, category, expense_policy
from tests.support.machine_reports import T, bought, cust, customer, idle, later, ok, report_body, setup_reports, submit
from tests.support.meter import unique_jpeg

PROFIT = "/api/v1/tenant/finance/profitability"


def _rows(f: FinCtx, group_by: str, first: str, last: str) -> dict[tuple[str, str], dict[str, Any]]:
    r = f.accountant.get(PROFIT, group_by=group_by, **{"from": first, "to": last})
    assert r.status_code == 200, r.text
    return {(row["label"], row["currency"]): row for row in r.json()["rows"]}


def _money(row: dict[str, Any], *keys: str) -> tuple[Decimal, ...]:
    return tuple(Decimal(row[k]) for k in keys)


def test_profitability_by_machine_customer_and_period(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    repair, fuel = category(f, "REPAIR", "Repairs"), category(f, "FUEL", "Fuel")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="50000")
    second = customer(f, "C2", "Second Ltd")
    bought(api, f, 7)
    bought(api, f, 2, customer_id=second)
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
        r = f.owner.post(f"{T}/expenses", body)
        assert r.status_code == 201, r.text
        out: dict[str, Any] = r.json()
        return out

    def decide(e: dict[str, Any], approve: bool) -> None:
        r = f.manager.post(f"{T}/approvals/{e['approval_request_id']}/decision", {"approve": approve})
        assert r.status_code == 200, r.text

    expense(repair, "30000", machine_id=m)  # auto-approved
    expense(repair, "45000", machine_id=m)  # auto-approved
    expense(repair, "70000", machine_id=m)  # pending: never counts
    decide(expense(repair, "60000", machine_id=m), False)  # rejected: never counts
    receipt = api.client.post(
        f"{T}/expense-receipts",
        headers=f.owner.headers(True, None),
        files={"file": ("r.jpg", unique_jpeg(), "image/jpeg")},
    ).json()["id"]
    usd = expense(repair, "10", machine_id=m, currency="USD", receipt_attachment_ids=[receipt])
    decide(usd, True)  # separate currency row
    bulk = expense(fuel, "3000000")
    decide(bulk, True)
    fe = f"{T}/fuel-events"
    for body in (
        {"event_type": "PURCHASE", "litres": "1000", "unit_price": "3000", "expense_id": bulk["id"]},  # to stock
        {"event_type": "ISSUE", "litres": "20", "unit_price": "3000", "machine_id": m},  # 60,000
        {"event_type": "PURCHASE", "litres": "10", "unit_price": "3100", "machine_id": m},  # 31,000
        {"event_type": "USAGE", "litres": "15", "machine_id": m},
    ):
        r = f.supervisor.post(fe, {**body, "occurred_at": at})
        assert r.status_code == 201, r.text

    # 9 engine hours: 6 for Road Builders, 2 for Second Ltd, 1 non-productive (no revenue). Approved on 2026-11-01.
    when = later(api, 9)
    rep = submit(
        f.supervisor,
        report_body(m, "1009", when, [cust(f.customer_id, 6), cust(second, 2), idle(ctx.reasons["BREAKDOWN"], 1)]),
    )
    pending = _rows(f, "MACHINE", "2026-11-01", "2026-11-01")
    assert all(Decimal(r["revenue"]) == 0 for r in pending.values())  # a submitted report earns nothing yet
    ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))

    machine = _rows(f, "MACHINE", "2026-11-01", "2026-11-01")
    [(label, _)] = [k for k in machine if k[1] == "TZS"]
    row = machine[(label, "TZS")]
    assert _money(row, "revenue", "net_revenue") == (Decimal(680000), Decimal(680000))
    assert _money(row, "expense_cost", "fuel_cost", "direct_cost", "margin") == (
        Decimal(75000),
        Decimal(91000),
        Decimal(166000),
        Decimal(514000),
    )
    assert {k: Decimal(v) for k, v in row["cost_by_category"].items()} == {"FUEL": 91000, "REPAIR": 75000}
    usd_row = machine[(label, "USD")]
    assert _money(usd_row, "net_revenue", "expense_cost", "margin") == (
        Decimal(0),
        Decimal(10),
        Decimal(-10),
    )  # never mixed

    by_customer = _rows(f, "CUSTOMER", "2026-11-01", "2026-11-01")
    assert _money(by_customer[("Road Builders Ltd", "TZS")], "net_revenue", "direct_cost", "margin") == (
        Decimal(510000),
        Decimal(0),
        Decimal(510000),
    )
    assert _money(by_customer[("Second Ltd", "TZS")], "net_revenue") == (Decimal(170000),)
    assert _money(by_customer[("Unattributed", "TZS")], "expense_cost", "fuel_cost", "margin") == (
        Decimal(75000),
        Decimal(91000),
        Decimal(-166000),
    )  # costs are per machine: not attributable to a customer

    # Revenue is recognized when a report is approved: the next day's report counts in its own period only.
    api.clock.set_at(datetime.fromisoformat("2026-11-02T08:00:00+00:00"))
    rep2 = submit(f.supervisor, report_body(m, "1010", api.clock.now + timedelta(minutes=1), [cust(f.customer_id, 1)]))
    ok(f.manager.post(f"{T}/machine-reports/{rep2['id']}/approve", {}))
    day2 = _rows(f, "CUSTOMER", "2026-11-02", "2026-11-02")[("Road Builders Ltd", "TZS")]
    assert _money(day2, "revenue", "net_revenue") == (Decimal(85000), Decimal(85000))
    both = _rows(f, "CUSTOMER", "2026-11-01", "2026-11-02")[("Road Builders Ltd", "TZS")]
    assert _money(both, "net_revenue") == (Decimal(595000),)
    assert _money(_rows(f, "CUSTOMER", "2026-11-01", "2026-11-01")[("Road Builders Ltd", "TZS")], "net_revenue") == (
        Decimal(510000),
    )
    assert f.supervisor.get(PROFIT, group_by="MACHINE", **{"from": "2026-11-01", "to": "2026-11-01"}).status_code == 403
