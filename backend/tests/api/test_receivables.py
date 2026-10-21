"""Gate 5 (R1-G): deposits/advances, partial payments and allocations, claimed vs verified settlement with
segregation of duties, customer balance and statement (opening, invoices, verified payments, closing)."""

from decimal import Decimal
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, complete_job, issue_invoice, setup_finance, tenant_sql

P = "/api/v1/tenant/customer-payments"


def _pay(f: FinCtx, actor: Actor, amount: str, method: str, ref: str | None, at: str, **kw: Any) -> dict[str, Any]:
    body = {"customer_id": f.customer_id, "amount": amount, "method": method, "reference": ref, "received_at": at, **kw}
    r = actor.post(P, body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def _decide(actor: Actor, payment_id: str, verified: bool) -> Any:
    return actor.post(f"{P}/{payment_id}/decision", {"verified": verified, "note": "bank statement checked"})


def _inv(f: FinCtx, inv_id: str) -> dict[str, Any]:
    out: dict[str, Any] = f.accountant.get(f"/api/v1/tenant/hire-invoices/{inv_id}").json()
    return out


def test_partial_payments_allocations_deposit_claims_and_statement(api: Api) -> None:
    f = setup_finance(api)
    # Advance received before the job (deposit): recorded by one accountant, verified by another person.
    deposit = _pay(f, f.accountant, "100000", "BANK", "DEP-1", "2026-10-30T10:00:00+00:00", note="Deposit")
    own = _decide(f.accountant, deposit["id"], True)
    assert own.status_code == 422 and own.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    assert _decide(f.supervisor, deposit["id"], True).status_code == 403  # supervisors cannot verify
    assert _decide(f.owner, deposit["id"], True).json()["status"] == "VERIFIED"
    assert _decide(f.accountant2, deposit["id"], False).json()["error"]["code"] == "PAYMENT_ALREADY_DECIDED"

    complete_job(api, f, f.c.job_id, "1000.0", "1008.0", 9, downtime_h=1.5)  # 6.5 h x 85,000
    inv = issue_invoice(f, [f.c.job_id])
    assert Decimal(inv["total"]) == Decimal("552500")

    partial = _pay(
        f,
        f.accountant,
        "200000",
        "MOBILE_MONEY",
        "MM-77",
        "2026-11-02T08:00:00+00:00",
        allocations=[{"invoice_id": inv["id"], "amount": "200000"}],
    )
    assert partial["status"] == "CLAIMED" and partial["allocations"][0]["amount"] == "200000.0000"
    claimed_view = _inv(f, inv["id"])
    assert (claimed_view["amount_paid"], claimed_view["payment_state"]) == ("0.0000", "UNPAID")  # claim != settled
    assert _decide(f.accountant2, partial["id"], True).json()["status"] == "VERIFIED"
    assert _inv(f, inv["id"])["payment_state"] == "PARTIALLY_PAID"
    events = tenant_sql(f.tid, "SELECT count(*) FROM outbox_event WHERE event_type = 'CustomerPaymentVerified'")
    assert events[0][0] == 2

    too_much = f.accountant.post(
        f"{P}/{deposit['id']}/allocations", {"allocations": [{"invoice_id": inv["id"], "amount": "100000.01"}]}
    )
    assert too_much.json()["error"]["code"] == "ALLOCATION_EXCEEDS_PAYMENT"
    applied = f.accountant.post(
        f"{P}/{deposit['id']}/allocations", {"allocations": [{"invoice_id": inv["id"], "amount": "100000"}]}
    )
    assert applied.status_code == 200, applied.text
    assert Decimal(_inv(f, inv["id"])["amount_paid"]) == Decimal("300000")

    over = f.accountant.post(
        P,
        {
            "customer_id": f.customer_id,
            "amount": "300000",
            "method": "BANK",
            "reference": "BK-9",
            "received_at": "2026-11-02T09:00:00+00:00",
            "allocations": [{"invoice_id": inv["id"], "amount": "300000"}],
        },
    )
    assert over.json()["error"]["code"] == "OVER_ALLOCATION"  # open amount is 252,500
    bounced = _pay(
        f,
        f.accountant,
        "252500",
        "BANK",
        "BK-9",
        "2026-11-02T09:00:00+00:00",
        allocations=[{"invoice_id": inv["id"], "amount": "252500"}],
    )
    rejected = _decide(f.accountant2, bounced["id"], False).json()
    assert rejected["status"] == "REJECTED" and rejected["allocations"][0]["released_at"] is not None
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
        "/api/v1/tenant/cash/collections",
        {"customer_id": f.customer_id, "amount": "50000", "received_at": "2026-11-02T12:00:00+00:00"},
    )
    assert cash.status_code == 201 and cash.json()["status"] == "CLAIMED" and cash.json()["method"] == "CASH"

    bal = f.accountant.get(f"/api/v1/tenant/customers/{f.customer_id}/balance").json()
    assert len(bal) == 1 and bal[0]["currency"] == "TZS"
    b = {
        k: Decimal(v) if isinstance(v, str) and k != "currency" and k != "customer_id" else v for k, v in bal[0].items()
    }
    assert (b["invoiced"], b["verified_payments"], b["balance"]) == (
        Decimal("552500"),
        Decimal("300000"),
        Decimal("252500"),
    )
    assert (b["unallocated_credit"], b["claimed_unverified"], b["open_invoices"]) == (0, Decimal("50000"), 1)

    st = f.accountant.get(
        f"/api/v1/tenant/customers/{f.customer_id}/statement", **{"from": "2026-11-01", "to": "2026-11-03"}
    ).json()
    assert Decimal(st["opening_balance"]) == Decimal("-100000")  # the deposit predates the period: credit
    assert [(x["kind"], x["reference"], Decimal(x["debit"]), Decimal(x["credit"])) for x in st["lines"]] == [
        ("INVOICE", inv["invoice_number"], Decimal("552500"), 0),
        ("PAYMENT", "MM-77", 0, Decimal("200000")),
    ]  # the rejected payment and the unverified cash claim are not settlement
    assert Decimal(st["closing_balance"]) == Decimal("252500") == Decimal(st["lines"][-1]["running_balance"])
    assert [p["amount"] for p in st["claimed_unverified"]] == ["50000.0000"]
    assert Decimal(st["claimed_unverified_total"]) == Decimal("50000")

    # Settle in full plus an advance for future work: the surplus is unallocated customer credit.
    final = _pay(
        f,
        f.accountant,
        "272500",
        "BANK",
        "BK-10",
        "2026-11-03T09:00:00+00:00",
        allocations=[{"invoice_id": inv["id"], "amount": "252500"}],
    )
    _decide(f.owner, final["id"], True)
    assert _inv(f, inv["id"])["payment_state"] == "PAID"
    end = f.accountant.get(f"/api/v1/tenant/customers/{f.customer_id}/balance").json()[0]
    assert (Decimal(end["balance"]), Decimal(end["unallocated_credit"]), end["open_invoices"]) == (
        Decimal("-20000"),
        Decimal("20000"),
        0,
    )
    listed = f.accountant.get(P, status="CLAIMED").json()
    assert [p["id"] for p in listed["items"]] == [cash.json()["id"]]
    # Claimed -> decided is final; evidence cannot be rewritten in the database either.
    rows = tenant_sql(f.tid, "SELECT status FROM customer_payment WHERE id = :i", i=final["id"])
    assert rows[0][0] == "VERIFIED"
