"""ADR-008 reports (CSV/PDF through the reports module): customer hours bought / used / left, productive vs
non-productive hours by machine and reason, sales and collections by method, credit invoices and their payments."""

import csv
import io
import uuid
from decimal import Decimal
from typing import Any

from httpx import Response

from tests.support.api import Api
from tests.support.hours import RATE
from tests.support.machine_reports import T, bought, cust, idle, later, ok, report_body, setup_reports, submit

R = f"{T}/reports"


def _csv(r: Response) -> list[dict[str, str]]:
    assert r.status_code == 200, r.text
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"), newline="")))


def _pay(api: Api, amount: Decimal | int, method: str) -> dict[str, Any]:
    return {
        "amount": str(amount),
        "method": method,
        "reference": None if method == "CASH" else f"REF-{uuid.uuid4().hex[:8]}",
        "received_at": api.clock.now.isoformat(),
    }


def test_owners_read_hours_money_and_credit_as_reports(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 6)  # bank, verified
    sale = ok(
        f.accountant.post(
            f"{T}/hours-purchases",
            {
                "customer_id": f.customer_id,
                "machine_id": m,
                "hours": "4",
                "payments": [_pay(api, RATE, "BANK"), {"method": "CREDIT", "amount": str(3 * RATE)}],
            },
        ),
        201,
    )
    inv = sale["credit_invoice"]
    ok(
        f.supervisor.post(
            f"{T}/credit-invoices/{inv['id']}/payments", {**_pay(api, RATE, "CASH"), "client_id": str(uuid.uuid4())}
        ),
        201,
    )
    rep = submit(
        f.supervisor,
        report_body(m, "1005", later(api, 5), [cust(f.customer_id, 4), idle(ctx.reasons["BREAKDOWN"], 1, "Hose")]),
    )
    ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))

    codes = {d["code"] for d in ok(f.owner.get(R))}
    assert {
        "customer_hours",
        "machine_hours",
        "sales_collections",
        "credit_invoices",
        "credit_invoice_payments",
    } <= codes
    assert "cash" in codes  # cash per supervisor

    [hours] = _csv(f.owner.get(f"{R}/customer_hours.csv"))
    assert hours["Customer"] == "Road Builders Ltd"
    assert Decimal(hours["Bought"]) == 10 and Decimal(hours["Activated"]) == 6 and Decimal(hours["Used"]) == 4
    assert Decimal(hours["Left"]) == 2 and Decimal(hours["Awaiting activation"]) == 4
    assert Decimal(hours["Credit owed"]) == 2 * RATE
    listed = ok(f.owner.get(f"{T}/customer-hours"))
    assert listed[0]["customer_name"] == "Road Builders Ltd" and Decimal(listed[0]["left"]) == 2

    rows = _csv(f.owner.get(f"{R}/machine_hours.csv"))
    assert [(r["Kind"], r["Reason"], Decimal(r["Hours"])) for r in rows] == [
        ("PRODUCTIVE", "Customer work", Decimal(4)),
        ("NON_PRODUCTIVE", "Breakdown / repair", Decimal(1)),
    ]
    assert Decimal(rows[0]["Share %"]) == 80 and Decimal(rows[1]["Machine total"]) == 5
    # The supervisor reads the machines assigned to them only (here: the same machine).
    assert len(_csv(f.supervisor.get(f"{R}/machine_hours.csv"))) == 2

    sales = {r["Method"]: r for r in _csv(f.owner.get(f"{R}/sales_collections.csv"))}
    assert Decimal(sales["BANK"]["Sold"]) == 7 * RATE and Decimal(sales["CREDIT"]["Sold"]) == 3 * RATE
    assert Decimal(sales["CASH"]["Collected"]) == RATE and Decimal(sales["CASH"]["Sold"]) == 0
    assert Decimal(sales["BANK"]["Collected"]) == 7 * RATE and Decimal(sales["BANK"]["Of which verified"]) == 6 * RATE

    [invoice] = _csv(f.owner.get(f"{R}/credit_invoices.csv"))
    assert invoice["Invoice"] == inv["invoice_number"] and invoice["Status"] == "PART_PAID"
    assert Decimal(invoice["Balance"]) == 2 * RATE
    [payment] = _csv(f.owner.get(f"{R}/credit_invoice_payments.csv"))
    assert payment["Method"] == "CASH" and Decimal(payment["Amount"]) == RATE and payment["Status"] == "CLAIMED"
    pdf = f.owner.get(f"{R}/machine_hours.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # Switched off customer hours: the hours and credit reports are neither listed nor exported.
    ok(
        f.owner.post(
            f"{T}/policies/CUSTOMER_HOURS/versions",
            {"scope": "TENANT", "values": {"enabled": False}, "reason": "Not selling hours"},
        ),
        201,
    )
    assert "credit_invoices" not in {d["code"] for d in ok(f.owner.get(R))}
    r = f.owner.get(f"{R}/credit_invoices.csv")
    assert r.status_code == 422 and r.json()["error"]["code"] == "HOURS_DISABLED"
