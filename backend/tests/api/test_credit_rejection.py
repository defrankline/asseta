"""Owner decision: "Reject credit". Someone who may activate credit (never the person who recorded the sale) rejects
the credit part of an order while nothing of it was activated and nothing was paid on its invoice. The invoice becomes
CANCELLED (reason kept, no longer owed or overdue, still listed), the credit hours are never activated and leave the
credit approvers' queue, paid parts of the order stay as they are, the seller is told why and phones drop the
invoice from their open invoices."""

import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import Response
from sqlalchemy.exc import DBAPIError

from tests.support.api import Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.hours import RATE, get_purchase, verify
from tests.support.machine_reports import code, field_credit, ok
from tests.support.notify import drain, member, sql

T = "/api/v1/tenant"
REASON = "Customer already owes too much"


def _pay(api: Api, amount: Decimal | int, method: str = "BANK") -> dict[str, Any]:
    return {
        "amount": str(amount),
        "method": method,
        "reference": None if method == "CASH" else f"REF-{uuid.uuid4().hex[:10]}",
        "received_at": api.clock.now.isoformat(),
    }


def _credit(amount: Decimal | int) -> dict[str, Any]:
    return {"amount": str(amount), "method": "CREDIT"}


def _sale(f: FinCtx, hours: int, lines: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "customer_id": f.customer_id,
        "machine_id": f.c.t.machine_id,
        "hours": str(hours),
        "client_id": str(uuid.uuid4()),
        "payments": lines,
    }


def _reject(actor: Any, purchase_id: str, reason: str = REASON) -> Response:
    r: Response = actor.post(f"{T}/hours-purchases/{purchase_id}/credit/reject", {"reason": reason})
    return r


def _queue(actor: Any, queue: str) -> set[str]:
    return {p["id"] for p in ok(actor.get(f"{T}/hours-purchases", queue=queue, page_size=100))["items"]}


def _csv(r: Response) -> list[dict[str, str]]:
    assert r.status_code == 200, r.text
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"), newline="")))


def test_rejecting_credit_cancels_the_invoice_and_keeps_the_paid_part(api: Api) -> None:
    f = setup_finance(api)
    seller = member(api, f.tid, "accountant", "acct-credit-seller")
    drain(api)
    p = ok(seller.post(f"{T}/hours-purchases", _sale(f, 10, [_pay(api, 4 * RATE), _credit(6 * RATE)])), 201)
    assert p["credit_status"] == "AWAITING_ACTIVATION" and p["credit_rejection"] is None
    assert p["id"] in _queue(f.owner, "CREDIT_TO_ACTIVATE")
    inv_id = p["credit_invoice"]["id"]

    done = ok(_reject(f.accountant2, p["id"]))
    assert done["credit_status"] == "REJECTED"
    rej = done["credit_rejection"]
    assert rej["reason"] == REASON and rej["rejected_by_name"] is not None and Decimal(rej["hours"]) == 6
    assert done["credit_invoice"]["status"] == "CANCELLED" and Decimal(done["credit_invoice"]["balance"]) == 0
    assert done["credit_invoice"]["rejection"]["reason"] == REASON
    # Only the paid part still waits (for its bank payment to be verified); the credit hours never will.
    assert Decimal(done["totals"]["awaiting_activation"]) == 4
    assert Decimal(done["totals"]["amount_outstanding"]) == 4 * RATE
    assert p["id"] not in _queue(f.owner, "CREDIT_TO_ACTIVATE")
    assert p["id"] in _queue(f.owner, "AWAITING_ACTIVATION")
    verify(f.accountant2, p["payments"][0]["id"])
    order = get_purchase(f.owner, p["id"])
    assert Decimal(order["totals"]["activated"]) == 4 and Decimal(order["totals"]["awaiting_activation"]) == 0
    assert order["status"] == "ACTIVE" and p["id"] not in _queue(f.owner, "AWAITING_ACTIVATION")
    assert Decimal(order["totals"]["amount_outstanding"]) == 0

    # The invoice: still listed (CANCELLED, reason kept), never owed, never overdue, never paid.
    inv = ok(f.owner.get(f"{T}/credit-invoices/{inv_id}"))
    assert inv["status"] == "CANCELLED" and Decimal(inv["balance"]) == 0 and inv["rejection"]["reason"] == REASON
    assert ok(f.owner.get(f"{T}/credit-invoices", status="CANCELLED"))["total"] == 1
    assert ok(f.owner.get(f"{T}/credit-invoices", status="UNPAID"))["total"] == 0
    api.clock.set_at(api.clock.now + timedelta(days=45))
    assert ok(f.owner.get(f"{T}/credit-invoices", overdue="true"))["total"] == 0
    r = f.accountant.post(f"{T}/credit-invoices/{inv_id}/payments", {**_pay(api, RATE), "client_id": str(uuid.uuid4())})
    assert r.status_code == 422 and code(r) == "INVOICE_CANCELLED", r.text
    balance = ok(f.owner.get(f"{T}/customers/{f.customer_id}/balance"))[0]
    assert Decimal(balance["invoiced"]) == 0 and Decimal(balance["balance"]) == 0 and balance["open_invoices"] == 0
    [hours] = ok(f.owner.get(f"{T}/customer-hours", customer_id=f.customer_id))
    assert Decimal(hours["credit_owed"]) == 0 and Decimal(hours["bought"]) == 4
    assert Decimal(hours["awaiting_activation"]) == 0
    [row] = _csv(f.owner.get(f"{T}/reports/credit_invoices.csv"))
    assert row["Status"] == "CANCELLED" and Decimal(row["Balance"]) == 0
    sales = {r["Method"]: r for r in _csv(f.owner.get(f"{T}/reports/sales_collections.csv"))}
    assert Decimal(sales.get("CREDIT", {}).get("Sold", "0")) == 0
    assert Decimal(sales.get("UNPAID", {}).get("Sold", "0")) == 0

    # Credit can no longer be activated on the order, and the rejection is final.
    r = f.accountant2.post(f"{T}/hours-purchases/{p['id']}/credit-activations", {"hours": "1", "reason": "Try"})
    assert r.status_code == 422 and code(r) == "CREDIT_REJECTED", r.text
    r = _reject(f.owner, p["id"])
    assert r.status_code == 422 and code(r) == "CREDIT_NOT_AWAITING", r.text

    # The stamp is set once: the database refuses changing or clearing it.
    for update in (
        "UPDATE credit_invoice SET rejection_reason = 'Changed' WHERE id = :i",
        "UPDATE credit_invoice SET rejected_at = NULL, rejection_reason = NULL WHERE id = :i",
        "DELETE FROM credit_invoice WHERE id = :i",
    ):
        with pytest.raises(DBAPIError, match="only a single rejection stamp"):
            sql(update, i=inv_id)

    # Audited, and the seller is told why.
    [(after, reason)] = tenant_sql(
        f.tid, "SELECT after, reason FROM audit_event WHERE action = 'hours.credit_rejected'"
    )
    assert reason == REASON and after["invoice_status"] == "CANCELLED"
    drain(api)
    [note] = [n for n in ok(seller.get(f"{T}/notifications"))["items"] if n["type"] == "HOURS_CREDIT_REJECTED"]
    assert note["body"] == f"Credit for Road Builders Ltd was not approved: {REASON}"
    assert note["data"]["record_id"] == p["id"]


def test_who_may_reject_credit(api: Api) -> None:
    f = setup_finance(api)
    p = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_credit(2 * RATE)])), 201)
    r = _reject(f.supervisor, p["id"])  # no tenant.hours.credit_activate
    assert r.status_code == 403, r.text
    r = _reject(f.accountant, p["id"])  # recorded the sale: never decides its credit
    assert r.status_code == 422 and code(r) == "SEGREGATION_OF_DUTIES", r.text
    r = _reject(f.accountant2, p["id"], "no")
    assert r.status_code == 422 and code(r) == "VALIDATION_FAILED", r.text
    r = f.accountant2.post(f"{T}/hours-purchases/{p['id']}/credit/reject", {})
    assert r.status_code == 422 and code(r) == "VALIDATION_FAILED", r.text
    paid = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 1, [_pay(api, RATE)])), 201)
    assert paid["credit_status"] is None
    r = _reject(f.accountant2, paid["id"])
    assert r.status_code == 422 and code(r) == "NO_CREDIT_PART", r.text
    assert get_purchase(f.owner, p["id"])["credit_invoice"]["status"] == "UNPAID"
    # The whole order was on credit: nothing is left to activate.
    done = ok(_reject(f.owner, p["id"]))
    assert done["status"] == "CREDIT_REJECTED" and Decimal(done["totals"]["awaiting_activation"]) == 0
    assert p["id"] not in _queue(f.owner, "AWAITING_ACTIVATION")


def test_refused_once_paid_on_the_invoice_or_activated_on_credit(api: Api) -> None:
    f = setup_finance(api)
    p = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 3, [_credit(3 * RATE)])), 201)
    inv_id = p["credit_invoice"]["id"]
    part = ok(
        f.accountant.post(
            f"{T}/credit-invoices/{inv_id}/payments", {**_pay(api, RATE), "client_id": str(uuid.uuid4())}
        ),
        201,
    )
    r = _reject(f.accountant2, p["id"])
    assert r.status_code == 422 and code(r) == "CREDIT_INVOICE_HAS_PAYMENTS", r.text
    # A rejected payment no longer pays the invoice: the credit can be rejected again.
    verify(f.accountant2, part["payments"][0]["payment_id"], ok=False)
    ok(_reject(f.accountant2, p["id"]))

    q = ok(f.accountant.post(f"{T}/hours-purchases", _sale(f, 2, [_credit(2 * RATE)])), 201)
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
    ok(f.accountant2.post(f"{T}/hours-purchases/{q['id']}/credit-activations", {"hours": "1", "reason": "On terms"}))
    r = _reject(f.owner, q["id"])
    assert r.status_code == 422 and code(r) == "CREDIT_NOT_AWAITING", r.text
    assert get_purchase(f.owner, q["id"])["credit_status"] == "ACTIVATED"


def test_phones_drop_the_rejected_invoice_from_open_invoices(api: Api) -> None:
    f = setup_finance(api, "Credit Reject Sync Co", "CRJ-1")
    field_credit(f)
    device = "android-credit-reject-001"
    headers = {**f.supervisor.headers(True, None), "X-Device-Id": device}
    ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=headers,
            json={"device_id": device, "platform": "ANDROID", "app_version": "2.0.0"},
        ),
        201,
    )
    p = ok(f.supervisor.post(f"{T}/hours-purchases", _sale(f, 2, [_pay(api, RATE, "CASH"), _credit(RATE)])), 201)

    def open_invoices() -> list[str]:
        data = ok(api.client.get("/api/v1/sync/changes", headers=headers, params={"cursor": 0}))["data"]
        return [i["id"] for i in data["open_credit_invoices"]]

    assert open_invoices() == [p["credit_invoice"]["id"]]
    ok(_reject(f.accountant2, p["id"]))
    assert open_invoices() == []
