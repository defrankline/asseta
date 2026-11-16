"""ADR-008 §1: orders with a CREDIT payment line. Credit is a line of the sale (amount only, registered customers, at
most one), recorded by people who may activate credit or - when the company allows it - by field staff. The sale
creates its credit invoice automatically (numbered, due after the customer's payment terms); the customer pays it in
full or in parts by cash, bank or mobile money, in the office or in the field (field cash goes into the recorder's
custody). Credit never makes hours usable by itself; paid money does, like any payment of the order."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.notification.reminders import run_reminders
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.hours import RATE, get_purchase, hours_policy, verify
from tests.support.machine_reports import code, field_credit, ok
from tests.support.notify import drain, member

T = "/api/v1/tenant"


def _pay(api: Api, amount: Decimal | int, method: str = "CASH") -> dict[str, Any]:
    return {
        "amount": str(amount),
        "method": method,
        "reference": None if method == "CASH" else f"REF-{uuid.uuid4().hex[:10]}",
        "received_at": api.clock.now.isoformat(),
    }


def _credit(amount: Decimal | int) -> dict[str, Any]:
    return {"amount": str(amount), "method": "CREDIT"}


def _sale(f: FinCtx, hours: int, lines: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "machine_id": f.c.t.machine_id,
        "hours": str(hours),
        "client_id": str(uuid.uuid4()),
        "payments": lines,
        **extra,
    }
    if "walk_in" not in extra and "customer_id" not in extra:
        body["customer_id"] = f.customer_id
    return body


def _invoice_payment(api: Api, amount: Decimal | int, method: str = "CASH", **extra: Any) -> dict[str, Any]:
    return {**_pay(api, amount, method), "client_id": str(uuid.uuid4()), **extra}


def _custody(actor: Actor) -> Decimal:
    rows = ok(actor.get(f"{T}/cash/custody/me"))
    return sum((Decimal(r["outstanding"]) for r in rows), Decimal(0))


# --- who may record a CREDIT line --------------------------------------------------------------------------------
def test_field_staff_record_credit_only_when_the_company_allows_it(api: Api) -> None:
    f = setup_finance(api)
    hours_policy(f, field_noncash_payments=True)
    body = _sale(f, 4, [_pay(api, 2 * RATE), _credit(2 * RATE)])
    r = f.supervisor.post(f"{T}/hours-purchases", body)
    assert r.status_code == 403 and code(r) == "CREDIT_SALES_NOT_ALLOWED", r.text
    assert tenant_sql(f.tid, "SELECT count(*) FROM hours_purchase")[0][0] == 0
    field_credit(f)
    p = ok(f.supervisor.post(f"{T}/hours-purchases", body), 201)
    assert Decimal(p["credit_amount"]) == 2 * RATE
    assert len(p["payments"]) == 1 and p["payments"][0]["method"] == "CASH"
    # People who may activate credit always may record it (the setting is about field staff).
    field_credit(f, on=False)
    office = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_credit(2 * RATE)])), 201)
    assert office["credit_invoice"]["status"] == "UNPAID"


def test_credit_is_for_registered_customers_one_line_and_within_the_total(api: Api) -> None:
    f = setup_finance(api)
    walk_in = _sale(f, 2, [_credit(2 * RATE)], walk_in={"name": "Passer-by", "phone": "+255700000001"})
    r = f.accountant.post(f"{T}/hours-purchases", walk_in)
    assert r.status_code == 422 and code(r) == "WALK_IN_NO_CREDIT", r.text
    r = f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_credit(RATE), _credit(RATE)]))
    assert r.status_code == 422 and code(r) == "VALIDATION_FAILED", r.text
    r = f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_pay(api, RATE, "BANK"), _credit(2 * RATE)]))
    assert code(r) == "PAYMENTS_EXCEED_TOTAL", r.text
    r = f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_pay(api, RATE), {"method": "CASH", "amount": "1"}]))
    assert r.status_code == 422, r.text  # money lines need received_at


def test_the_sale_invoices_the_credit_part_and_credit_activates_nothing(api: Api) -> None:
    f = setup_finance(api)
    p = ok(
        f.accountant.post(f"{T}/hours-purchases", _sale(f, 10, [_pay(api, 4 * RATE, "BANK"), _credit(6 * RATE)])), 201
    )
    inv = p["credit_invoice"]
    assert inv["invoice_number"] == "CI-2026-00001" and Decimal(inv["amount"]) == 6 * RATE
    assert inv["status"] == "UNPAID" and inv["overdue"] is False
    assert date.fromisoformat(inv["due_date"]) == api.clock.now.date() + timedelta(days=30)  # the customer's terms
    detail = ok(f.owner.get(f"{T}/credit-invoices/{inv['id']}"))
    assert Decimal(detail["hours"]) == 6 and Decimal(detail["unit_price"]) == RATE
    assert detail["purchase_number"] == p["purchase_number"] and detail["customer_name"] == "Road Builders Ltd"
    # Nothing is usable until money is verified or someone activates the credit part.
    assert Decimal(p["totals"]["activated"]) == 0
    verify(f.accountant2, p["payments"][0]["id"])
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["activated"]) == 4
    # The credit part goes through the existing credit activation, within the customer's credit limit.
    arr = ok(
        f.manager.post(
            f"{T}/credit-arrangements",
            {
                "customer_id": f.customer_id,
                "limit_amount": str(10 * RATE),
                "effective_from": "2026-11-01",
                "reason": "Trusted customer",
            },
        ),
        201,
    )
    ok(f.owner.post(f"{T}/credit-arrangements/{arr['id']}/decision", {"approve": True}))
    ok(
        f.accountant2.post(
            f"{T}/hours-purchases/{p['id']}/credit-activations", {"hours": "6", "reason": "Customer pays on terms"}
        )
    )
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["activated"]) == 10
    # A paid order gets no invoice.
    paid = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 1, [_pay(api, RATE, "BANK")])), 201)
    assert paid["credit_invoice"] is None and paid["credit_amount"] is None


# --- paying the invoice ------------------------------------------------------------------------------------------
def test_the_invoice_is_paid_in_parts_by_any_method_and_field_cash_goes_into_custody(api: Api) -> None:
    f = setup_finance(api)
    p = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 6, [_credit(6 * RATE)])), 201)
    inv_id = p["credit_invoice"]["id"]
    before = _custody(f.supervisor)

    # The supervisor collects cash in the field: it is in their custody like any collection.
    part = ok(f.supervisor.post(f"{T}/credit-invoices/{inv_id}/payments", _invoice_payment(api, 2 * RATE)), 201)
    assert part["status"] == "PART_PAID" and Decimal(part["balance"]) == 4 * RATE
    assert part["payments"][0]["method"] == "CASH" and part["payments"][0]["collection_number"].startswith("COL-")
    assert _custody(f.supervisor) == before + 2 * RATE
    # Field staff record bank / mobile money only when the company allows field non-cash payments.
    r = f.supervisor.post(f"{T}/credit-invoices/{inv_id}/payments", _invoice_payment(api, RATE, "MOBILE_MONEY"))
    assert r.status_code == 403 and code(r) == "PAYMENT_NOT_PERMITTED", r.text
    hours_policy(f, field_noncash_payments=True)
    ok(f.supervisor.post(f"{T}/credit-invoices/{inv_id}/payments", _invoice_payment(api, RATE, "MOBILE_MONEY")), 201)
    # The office records a bank part; more than the balance is refused.
    r = f.accountant.post(f"{T}/credit-invoices/{inv_id}/payments", _invoice_payment(api, 4 * RATE, "BANK"))
    assert r.status_code == 422 and code(r) == "INVOICE_OVERPAYMENT", r.text
    done = ok(f.accountant.post(f"{T}/credit-invoices/{inv_id}/payments", _invoice_payment(api, 3 * RATE, "BANK")), 201)
    assert done["status"] == "PAID" and Decimal(done["balance"]) == 0
    assert sorted(x["method"] for x in done["payments"]) == ["BANK", "CASH", "MOBILE_MONEY"]
    r = f.accountant.post(f"{T}/credit-invoices/{inv_id}/payments", _invoice_payment(api, 1, "BANK"))
    assert code(r) == "INVOICE_PAID", r.text
    # The money pays the order: once verified it makes the hours usable.
    for x in done["payments"]:
        verify(f.accountant2, x["payment_id"])
    order = get_purchase(f.owner, p["id"])
    assert Decimal(order["totals"]["activated"]) == 6 and order["credit_invoice"]["status"] == "PAID"
    assert Decimal(ok(f.owner.get(f"{T}/credit-invoices/{inv_id}"))["paid_verified"]) == 6 * RATE
    # A rejected payment no longer pays the invoice.
    p2 = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 1, [_credit(RATE)])), 201)
    inv2 = p2["credit_invoice"]["id"]
    bank = ok(f.accountant.post(f"{T}/credit-invoices/{inv2}/payments", _invoice_payment(api, RATE, "BANK")), 201)
    assert bank["status"] == "PAID"
    verify(f.accountant2, bank["payments"][0]["payment_id"], ok=False)
    after = ok(f.owner.get(f"{T}/credit-invoices/{inv2}"))
    assert after["status"] == "UNPAID" and after["payments"][0]["counts"] is False


def test_invoices_list_by_status_and_overdue_and_the_office_is_told(api: Api) -> None:
    f = setup_finance(api)
    office = member(api, f.tid, "accountant", "acct-credit-overdue")
    approver = member(api, f.tid, "accountant", "acct-credit-sale")
    drain(api)
    p = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_credit(2 * RATE)])), 201)
    drain(api)
    note = next(n for n in ok(approver.get(f"{T}/notifications"))["items"] if n["type"] == "HOURS_CREDIT_TO_ACTIVATE")
    assert p["purchase_number"] in note["title"] and "fraud" not in note["body"].lower()
    inv = p["credit_invoice"]
    assert ok(f.owner.get(f"{T}/credit-invoices", status="UNPAID"))["total"] == 1
    assert ok(f.owner.get(f"{T}/credit-invoices", overdue="true"))["total"] == 0
    # Past the due date with a balance: overdue, and the office is reminded once.
    api.clock.set_at(api.clock.now + timedelta(days=31))
    overdue = ok(f.owner.get(f"{T}/credit-invoices", overdue="true"))["items"]
    assert [i["id"] for i in overdue] == [inv["id"]] and overdue[0]["days_overdue"] == 1
    assert ok(f.owner.get(f"{T}/credit-invoices", customer_id=f.customer_id, q=inv["invoice_number"]))["total"] == 1
    for _ in range(2):
        run_reminders(get_sessionmaker(), api.clock.now)
    told = [n for n in ok(office.get(f"{T}/notifications"))["items"] if n["type"] == "CREDIT_INVOICE_OVERDUE"]
    assert len(told) == 1 and inv["invoice_number"] in told[0]["title"]
    ok(f.accountant.post(f"{T}/credit-invoices/{inv['id']}/payments", _invoice_payment(api, 2 * RATE, "BANK")), 201)
    assert ok(f.owner.get(f"{T}/credit-invoices", overdue="true"))["total"] == 0
    assert ok(f.owner.get(f"{T}/credit-invoices", status="PAID"))["total"] == 1


def test_a_cancelled_order_cancels_its_invoice(api: Api) -> None:
    f = setup_finance(api)
    p = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_credit(2 * RATE)])), 201)
    req = ok(f.manager.post(f"{T}/hours-purchases/{p['id']}/cancellation", {"reason": "Customer changed plans"}), 201)
    ok(f.owner.post(f"{T}/hours-cancellations/{req['id']}/decision", {"approve": True}))
    inv = ok(f.owner.get(f"{T}/credit-invoices/{p['credit_invoice']['id']}"))
    assert inv["status"] == "CANCELLED" and Decimal(inv["balance"]) == 0
    r = f.accountant.post(f"{T}/credit-invoices/{inv['id']}/payments", _invoice_payment(api, RATE, "BANK"))
    assert code(r) == "INVOICE_CANCELLED", r.text
