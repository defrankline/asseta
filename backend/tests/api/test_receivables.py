"""Gate 5 (R1-G) on credit invoices (ADR-008 §1): deposits/advances, partial payments of a credit invoice, claimed vs
verified settlement with segregation of duties, customer balance and statement (opening, invoices, verified payments,
closing)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.hours import RATE

P = "/api/v1/tenant/customer-payments"
T = "/api/v1/tenant"


def _pay(f: FinCtx, actor: Actor, amount: str, method: str, ref: str | None, at: str, **kw: Any) -> dict[str, Any]:
    body = {"customer_id": f.customer_id, "amount": amount, "method": method, "reference": ref, "received_at": at, **kw}
    r = actor.post(P, body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def _decide(actor: Actor, payment_id: str, verified: bool) -> Any:
    return actor.post(f"{P}/{payment_id}/decision", {"verified": verified, "note": "bank statement checked"})


def _credit_sale(api: Api, f: FinCtx, hours: int) -> dict[str, Any]:
    body = {
        "customer_id": f.customer_id,
        "machine_id": f.c.t.machine_id,
        "hours": str(hours),
        "client_id": str(uuid.uuid4()),
        "payments": [{"amount": str(hours * RATE), "method": "CREDIT"}],
    }
    r = f.accountant.post(f"{T}/hours-purchases", body)
    assert r.status_code == 201, r.text
    inv: dict[str, Any] = r.json()["credit_invoice"]
    return inv


def _pay_invoice(f: FinCtx, inv_id: str, amount: str, method: str, ref: str, at: str) -> dict[str, Any]:
    body = {"client_id": str(uuid.uuid4()), "amount": amount, "method": method, "reference": ref, "received_at": at}
    r = f.accountant.post(f"{T}/credit-invoices/{inv_id}/payments", body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def _payment_id(inv: dict[str, Any], ref: str) -> str:
    return str(next(x["payment_id"] for x in inv["payments"] if x["reference"] == ref))


def _inv(f: FinCtx, inv_id: str) -> dict[str, Any]:
    out: dict[str, Any] = f.accountant.get(f"{T}/credit-invoices/{inv_id}").json()
    return out


def test_partial_payments_deposit_claims_and_statement(api: Api) -> None:
    f = setup_finance(api)
    # Advance received before any sale (deposit): recorded by one accountant, verified by another person.
    deposit = _pay(f, f.accountant, "100000", "BANK", "DEP-1", "2026-10-30T10:00:00+00:00", note="Deposit")
    own = _decide(f.accountant, deposit["id"], True)
    assert own.status_code == 422 and own.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    assert _decide(f.supervisor, deposit["id"], True).status_code == 403  # supervisors cannot verify
    assert _decide(f.owner, deposit["id"], True).json()["status"] == "VERIFIED"
    assert _decide(f.accountant2, deposit["id"], False).json()["error"]["code"] == "PAYMENT_ALREADY_DECIDED"

    api.clock.set_at(datetime.fromisoformat("2026-11-02T07:00:00+00:00"))
    inv = _credit_sale(api, f, 6)  # 6 h x 85,000 on credit
    assert Decimal(inv["amount"]) == Decimal("510000")

    paid = _pay_invoice(f, inv["id"], "200000", "MOBILE_MONEY", "MM-77", "2026-11-02T08:00:00+00:00")
    partial = _payment_id(paid, "MM-77")
    assert Decimal(_inv(f, inv["id"])["paid_verified"]) == 0  # a claim is not settlement
    assert _decide(f.accountant2, partial, True).json()["status"] == "VERIFIED"
    assert Decimal(_inv(f, inv["id"])["paid_verified"]) == Decimal("200000")
    events = tenant_sql(f.tid, "SELECT count(*) FROM outbox_event WHERE event_type = 'CustomerPaymentVerified'")
    assert events[0][0] == 2

    over = f.accountant.post(
        f"{T}/credit-invoices/{inv['id']}/payments",
        {
            "amount": "310001",
            "method": "BANK",
            "reference": "BK-8",
            "received_at": "2026-11-02T09:00:00+00:00",
        },
    )
    assert over.json()["error"]["code"] == "INVOICE_OVERPAYMENT"  # open amount is 310,000
    bounced = _pay_invoice(f, inv["id"], "310000", "BANK", "BK-9", "2026-11-02T09:00:00+00:00")
    rejected = _decide(f.accountant2, _payment_id(bounced, "BK-9"), False).json()
    assert rejected["status"] == "REJECTED"
    assert _inv(f, inv["id"])["status"] == "PART_PAID"  # the rejected payment no longer pays it
    dup = f.accountant.post(
        P,
        {
            "customer_id": f.customer_id,
            "amount": "1",
            "method": "BANK",
            "reference": "BK-9",
            "received_at": "2026-11-02T09:00:00+00:00",
        },
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "DUPLICATE_PAYMENT_REFERENCE"
    no_ref = f.accountant.post(
        P, {"customer_id": f.customer_id, "amount": "1", "method": "BANK", "received_at": "2026-11-02T09:00:00+00:00"}
    )
    assert no_ref.status_code == 422

    # A supervisor's cash collection is a claim until the office verifies it.
    cash = f.supervisor.post(
        f"{T}/cash/collections",
        {"customer_id": f.customer_id, "amount": "50000", "received_at": "2026-11-02T12:00:00+00:00"},
    )
    assert cash.status_code == 201 and cash.json()["status"] == "CLAIMED" and cash.json()["method"] == "CASH"

    bal = f.accountant.get(f"{T}/customers/{f.customer_id}/balance").json()
    assert len(bal) == 1 and bal[0]["currency"] == "TZS"
    b = {
        k: Decimal(v) if isinstance(v, str) and k != "currency" and k != "customer_id" else v for k, v in bal[0].items()
    }
    assert (b["invoiced"], b["verified_payments"], b["balance"]) == (
        Decimal("510000"),
        Decimal("200000"),
        Decimal("310000"),
    )
    # The verified deposit is not linked to anything: it is the customer's unallocated credit.
    assert (b["unallocated_credit"], b["claimed_unverified"], b["open_invoices"]) == (
        Decimal("100000"),
        Decimal("50000"),
        1,
    )

    st = f.accountant.get(
        f"{T}/customers/{f.customer_id}/statement", **{"from": "2026-11-01", "to": "2026-11-03"}
    ).json()
    assert Decimal(st["opening_balance"]) == 0
    assert [(x["kind"], x["reference"], Decimal(x["debit"]), Decimal(x["credit"])) for x in st["lines"]] == [
        ("INVOICE", inv["invoice_number"], Decimal("510000"), 0),
        ("PAYMENT", "MM-77", 0, Decimal("200000")),
    ]  # the rejected payment and the unverified cash claim are not settlement
    assert Decimal(st["closing_balance"]) == Decimal("310000") == Decimal(st["lines"][-1]["running_balance"])
    assert [p["amount"] for p in st["claimed_unverified"]] == ["50000.0000"]
    assert Decimal(st["claimed_unverified_total"]) == Decimal("50000")
    later = f.accountant.get(
        f"{T}/customers/{f.customer_id}/statement", **{"from": "2026-11-03", "to": "2026-11-04"}
    ).json()
    assert Decimal(later["opening_balance"]) == Decimal("310000") and later["lines"] == []

    # Settle in full: the invoice is paid and nothing is open.
    final = _pay_invoice(f, inv["id"], "310000", "BANK", "BK-10", "2026-11-03T09:00:00+00:00")
    _decide(f.owner, _payment_id(final, "BK-10"), True)
    assert _inv(f, inv["id"])["status"] == "PAID"
    end = f.accountant.get(f"{T}/customers/{f.customer_id}/balance").json()[0]
    assert (Decimal(end["balance"]), Decimal(end["unallocated_credit"]), end["open_invoices"]) == (
        Decimal("0"),
        Decimal("100000"),
        0,
    )
    listed = f.accountant.get(P, status="CLAIMED").json()
    assert [p["id"] for p in listed["items"]] == [cash.json()["id"]]
    # Claimed -> decided is final; evidence cannot be rewritten in the database either.
    rows = tenant_sql(f.tid, "SELECT status FROM customer_payment WHERE reference = 'BK-10'")
    assert rows[0][0] == "VERIFIED"
