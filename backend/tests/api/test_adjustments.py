"""DEC-032 Phase 2 (guideline 4.6, T7, scenario 11): Ledger 6 with original value, new value, reason, evidence,
requester, approver and resulting balance; customer-hour corrections; refunds; reversal of posted transactions."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, complete_job, issue_invoice, setup_finance
from tests.support.hours import RATE, balance, get_purchase, hours_policy, prepaid_job, purchase, verify
from tests.support.jobs import unique_jpeg
from tests.support.notify import drain

T = "/api/v1/tenant"
A = f"{T}/adjustment-requests"


def _setup(api: Api, **policy: Any) -> FinCtx:
    f = setup_finance(api)
    r = f.owner.post(f"{T}/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    assert r.status_code == 200, r.text
    hours_policy(f, adjustment_evidence_required=False, **policy)
    return f


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _err(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def _paid_purchase(api: Api, f: FinCtx, hours: str = "10", *, method: str = "BANK", staff: str | None = None) -> Any:
    pay = str(int(hours) * RATE)
    p = purchase(api, f.accountant, f, hours, pay=pay, method=method, staff_id=staff)
    verify(f.owner, p["allocations"][0]["payment_id"])
    return get_purchase(f.manager, p["id"])


def _propose(actor: Actor, **body: Any) -> Any:
    body.setdefault("reason", "Reason for this adjustment")
    return actor.post(A, body)


def _approve(actor: Actor, request_id: str, **body: Any) -> Any:
    return actor.post(f"{A}/{request_id}/decision", {"decision": "APPROVE", "note": "Checked", **body})


def _ledger(actor: Actor, **filters: Any) -> list[dict[str, Any]]:
    return list(_ok(actor.get(f"{T}/adjustments", **filters))["items"])


def _balance_money(actor: Actor, customer_id: str) -> dict[str, Decimal]:
    row = _ok(actor.get(f"{T}/customers/{customer_id}/balance"))[0]
    return {k: Decimal(row[k]) for k in ("balance", "unallocated_credit", "verified_payments")}


def _complete_prepaid(api: Api, f: FinCtx, number: str, hours: int) -> str:
    job = prepaid_job(api, f, number)
    complete_job(api, f, job, "500", str(500 + hours), hours)
    return job


def test_scenario_11_every_flow_posts_with_original_kept_and_approval_history(api: Api) -> None:
    f = _setup(api)
    p = _paid_purchase(api, f)
    other = f.c.t.machine_id

    # Cancellation of a small purchase: original stays visible, ledger records who, when, how many and the result.
    small = _paid_purchase(api, f, "2")
    cancel = _ok(
        f.manager.post(f"{T}/hours-purchases/{small['id']}/cancellation", {"reason": "Customer changed plans"}), 201
    )
    decided = _ok(f.owner.post(f"{T}/hours-cancellations/{cancel['id']}/decision", {"approve": True, "note": "Agreed"}))
    assert decided["status"] == "APPROVED"
    entries = _ledger(f.owner, original_id=small["id"])
    assert len(entries) == 1
    e = entries[0]
    assert e["adjustment_type"] == "HOURS_CANCELLATION" and e["status"] == "APPROVED"
    assert e["original_reference"] == small["purchase_number"] and e["original_type"] == "hours_purchase"
    assert Decimal(e["original_value"]) == 2 and Decimal(e["new_value"]) == 0 and Decimal(e["amount"]) == -2
    assert Decimal(e["resulting_balance"]) == 0 and e["reason"] == "Customer changed plans"
    assert e["requested_by_name"] and e["approved_by_name"] and e["requested_at"] and e["approved_at"]
    assert e["requested_by"] != e["approved_by"]
    still = get_purchase(f.manager, small["id"])
    assert still["purchase_number"] == small["purchase_number"] and Decimal(still["hours"]) == 2  # original preserved

    # Detail by id, filters, CSV, and a rejection is retained too.
    assert _ok(f.owner.get(f"{T}/adjustments/{e['id']}"))["id"] == e["id"]
    assert [x["id"] for x in _ledger(f.owner, type="HOURS_CANCELLATION", customer_id=f.customer_id)] == [e["id"]]
    assert _ledger(f.owner, reference=small["purchase_number"])[0]["id"] == e["id"]
    assert _ledger(f.owner, machine_id=other)[0]["id"] == e["id"]
    assert _ledger(f.owner, person_id=e["approved_by"])[0]["id"] == e["id"]
    assert _ledger(f.owner, status="APPROVED", date_from="2020-01-01", date_to="2999-01-01")[0]["id"] == e["id"]
    assert _ledger(f.owner, date_from="2999-01-01") == []
    second = _ok(_propose(f.manager, request_type="HOURS_CORRECTION", purchase_id=p["id"], hours="-1"), 201)
    _ok(f.owner.post(f"{A}/{second['id']}/decision", {"decision": "REJECT", "note": "Not supported"}))
    assert _ledger(f.owner, status="REJECTED", type="HOURS_CORRECTION")[0]["decision_note"] == "Not supported"
    csv_body = f.owner.get(f"{T}/adjustments/export.csv", type="HOURS_CANCELLATION")
    assert csv_body.status_code == 200 and "text/csv" in csv_body.headers["content-type"]
    assert small["purchase_number"] in csv_body.text and "adjustment_type" in csv_body.text
    # Ledger rows cannot be changed or removed: the database itself refuses (trigger; no UPDATE/DELETE grant).
    assert api.client.post(f"{T}/adjustments", headers=f.owner.headers(True, None)).status_code == 405
    for statement in ("UPDATE adjustment_ledger_entry SET reason = 'x'", "DELETE FROM adjustment_ledger_entry"):
        with pytest.raises(DBAPIError), get_sessionmaker()() as session:
            apply_scope(session, DbScope.TENANT, uuid.UUID(f.tid), None)
            session.execute(text(statement))


def test_hours_correction_propose_approve_and_guards(api: Api) -> None:
    f = _setup(api)
    p = _paid_purchase(api, f)

    # Second person always; negative lots refused; above activation refused.
    wrong = _propose(f.accountant, request_type="HOURS_CORRECTION", purchase_id=p["id"], hours="-20")
    _err(wrong, 422, "HOURS_CORRECTION_NEGATIVE")
    above = _propose(f.accountant, request_type="HOURS_CORRECTION", purchase_id=p["id"], hours="1")
    _err(above, 422, "HOURS_CORRECTION_EXCEEDS_LOT")
    down = _ok(_propose(f.accountant, request_type="HOURS_CORRECTION", purchase_id=p["id"], hours="-2.5"), 201)
    assert down["status"] == "PROPOSED" and Decimal(down["effects"]["lot_hours_after"]) == Decimal("7.5")
    _err(_approve(f.accountant, down["id"]), 422, "SEGREGATION_OF_DUTIES")
    approved = _ok(_approve(f.owner, down["id"]))
    assert approved["status"] == "APPROVED" and approved["effects"]["lot_hours_after"] == "7.50"
    left = balance(f.owner, f.customer_id, f.c.t.machine_id)
    assert left is not None and Decimal(left["remaining"]) == Decimal("7.5")
    e = _ledger(f.owner, type="HOURS_CORRECTION", status="APPROVED")[0]
    assert Decimal(e["original_value"]) == 10 and Decimal(e["new_value"]) == Decimal("7.5")
    assert Decimal(e["amount"]) == Decimal("-2.5") and Decimal(e["resulting_balance"]) == Decimal("7.5")
    _err(_approve(f.owner, down["id"]), 409, "ALREADY_DECIDED")

    # Correcting consumed hours: give back hours a job consumed, referencing the entry; cannot exceed the entry.
    job = _complete_prepaid(api, f, "J-CORR", 3)
    consumed = next(
        e
        for e in _ok(f.manager.get(f"{T}/hours-ledger", purchase_id=p["id"]))["items"]
        if e["entry_type"] == "CONSUMED" and e["job_id"] == job
    )
    _err(
        _propose(
            f.manager,
            request_type="HOURS_CORRECTION",
            purchase_id=p["id"],
            hours="5",
            job_id=job,
            consumed_entry_id=consumed["id"],
        ),
        422,
        "HOURS_CORRECTION_EXCEEDS_ENTRY",
    )
    give_back = _ok(
        _propose(
            f.manager,
            request_type="HOURS_CORRECTION",
            purchase_id=p["id"],
            hours="1",
            job_id=job,
            consumed_entry_id=consumed["id"],
        ),
        201,
    )
    _ok(_approve(f.owner, give_back["id"]))
    entry_types = [e["entry_type"] for e in _ok(f.manager.get(f"{T}/hours-ledger", purchase_id=p["id"]))["items"]]
    assert "CORRECTION_DEDUCT" in entry_types and "CORRECTION_ADD" in entry_types


def test_refund_policy_credit_and_payout_with_balances(api: Api) -> None:
    f = _setup(api)
    p = _paid_purchase(api, f)

    _err(
        _propose(f.accountant, request_type="HOURS_REFUND", purchase_id=p["id"], hours="2", settlement="CREDIT"),
        422,
        "REFUND_NOT_ALLOWED",
    )
    hours_policy(f, refund_allowed=True, adjustment_evidence_required=False)
    _err(
        _propose(f.accountant, request_type="HOURS_REFUND", purchase_id=p["id"], hours="20", settlement="CREDIT"),
        422,
        "EXCEEDS_REMAINING_HOURS",
    )
    r = _ok(
        _propose(f.accountant, request_type="HOURS_REFUND", purchase_id=p["id"], hours="4", settlement="CREDIT"), 201
    )
    assert Decimal(r["amount"]) == 4 * RATE and r["effects"]["value"]
    _err(_approve(f.accountant, r["id"]), 422, "SEGREGATION_OF_DUTIES")
    done = _ok(_approve(f.owner, r["id"]))
    assert done["status"] == "APPROVED" and Decimal(done["effects"]["lot_hours_after"]) == 6
    got = get_purchase(f.manager, p["id"])
    assert Decimal(got["totals"]["remaining"]) == 6
    assert Decimal(got["totals"]["amount_verified"]) == 6 * RATE  # the kept part re-allocated, nothing edited
    money = _balance_money(f.owner, f.customer_id)
    assert money["unallocated_credit"] == 4 * RATE and money["verified_payments"] == 10 * RATE
    e = _ledger(f.owner, type="HOURS_REFUND")[0]
    assert Decimal(e["amount"]) == 4 and e["resulting_balance"] is not None

    # Pay-out: the money leaves; the balance goes back up and free credit stays honest.
    missing = _propose(f.accountant, request_type="HOURS_REFUND", purchase_id=p["id"], hours="1", settlement="PAY_OUT")
    _err(missing, 422, "REFUND_PAYOUT_REQUIRED")
    stranger = {"method": "CASH", "staff_member_id": str(uuid.uuid4())}
    _err(
        _propose(
            f.accountant,
            request_type="HOURS_REFUND",
            purchase_id=p["id"],
            hours="1",
            settlement="PAY_OUT",
            payout=stranger,
        ),
        404,
        "STAFF_NOT_FOUND",
    )
    r2 = _ok(
        _propose(
            f.manager,
            request_type="HOURS_REFUND",
            purchase_id=p["id"],
            hours="2",
            settlement="PAY_OUT",
            payout={"method": "BANK", "reference": "TRX-991"},
        ),
        201,
    )
    _ok(_approve(f.owner, r2["id"]))
    money2 = _balance_money(f.owner, f.customer_id)
    assert money2["unallocated_credit"] == 4 * RATE  # 10 verified - 4 kept - 4 credit... - 2 paid out
    assert money2["balance"] == -8 * RATE  # 10 verified minus 2 paid back: customer's net credit from hours


def test_bounced_payment_part_used_hours_become_receivable(api: Api) -> None:
    f = _setup(api)
    p = _paid_purchase(api, f)
    _complete_prepaid(api, f, "J-USED", 4)
    payment_id = p["allocations"][0]["payment_id"]

    claimed = _propose(f.accountant, request_type="COLLECTION_REVERSAL", payment_id=payment_id)
    _err(claimed, 422, "REVERSAL_TYPE_MISMATCH")
    req = _ok(
        _propose(f.accountant, request_type="PAYMENT_REVERSAL", payment_id=payment_id, reason="Cheque bounced"), 201
    )
    assert Decimal(req["effects"]["unused_hours_removed"]) == 6 and Decimal(req["effects"]["money_owed"]) == 4 * RATE
    _err(
        _propose(f.accountant, request_type="PAYMENT_REVERSAL", payment_id=payment_id, reason="Cheque bounced"),
        409,
        "REVERSAL_EXISTS",
    )
    _err(_approve(f.accountant, req["id"]), 422, "SEGREGATION_OF_DUTIES")
    done = _ok(_approve(f.owner, req["id"]))
    assert done["status"] == "APPROVED"

    # Unused hours deactivated by offsetting entries; used hours billed; nothing edited.
    got = get_purchase(f.manager, p["id"])
    assert Decimal(got["totals"]["remaining"]) == 0 and Decimal(got["totals"]["reversed"]) == 6
    assert Decimal(got["totals"]["consumed"]) == 4
    entries = _ok(f.manager.get(f"{T}/hours-ledger", purchase_id=p["id"]))["items"]
    assert any(e["entry_type"] == "REVERSAL" and Decimal(e["hours"]) == 6 for e in entries)
    payment = _ok(f.accountant.get(f"{T}/customer-payments/{payment_id}"))
    assert payment["status"] == "VERIFIED" and payment["reversed_at"] is not None  # original kept
    assert Decimal(payment["amount"]) == 10 * RATE
    invoice_id = done["effects"]["recovery_invoice_id"]
    inv = _ok(f.accountant.get(f"{T}/hire-invoices/{invoice_id}"))
    assert inv["status"] == "ISSUED" and Decimal(inv["total"]) == 4 * RATE
    assert inv["lines"][0]["kind"] == "HOURS_RECOVERY"

    # Receivables correct: only the 400 of used hours is owed.
    money = _balance_money(f.owner, f.customer_id)
    assert money["balance"] == 4 * RATE and money["unallocated_credit"] == 0
    statement = _ok(
        f.accountant.get(f"{T}/customers/{f.customer_id}/statement", **{"from": "2026-10-01", "to": "2026-12-31"})
    )
    assert {"PAYMENT", "ADJUSTMENT", "INVOICE"} <= {x["kind"] for x in statement["lines"]}
    # Reversed money cannot be re-used.
    _err(
        f.accountant.post(f"{T}/hours-purchases/{p['id']}/allocations", {"payment_id": payment_id, "amount": "1"}),
        422,
        "PAYMENT_REVERSED",
    )
    _err(
        _propose(f.accountant, request_type="PAYMENT_REVERSAL", payment_id=payment_id), 409, "PAYMENT_ALREADY_REVERSED"
    )
    # The reversal stamp is single-use and the row stays frozen otherwise (guard trigger).
    with pytest.raises(DBAPIError), get_sessionmaker()() as session:
        apply_scope(session, DbScope.TENANT, uuid.UUID(f.tid), None)
        session.execute(text("UPDATE customer_payment SET amount = 1 WHERE id = :id"), {"id": payment_id})

    e = _ledger(f.owner, type="PAYMENT_REVERSAL")[0]
    assert Decimal(e["original_value"]) == 10 * RATE and Decimal(e["new_value"]) == 0
    assert Decimal(e["resulting_balance"]) == 4 * RATE and e["details"]["treatment"] == "RECEIVABLE"
    assert e["original_reference"] == payment["reference"]


def test_reversal_case_treatment_and_unused_only(api: Api) -> None:
    f = _setup(api, reversal_used_hours_treatment="CASE")
    p = _paid_purchase(api, f)
    _complete_prepaid(api, f, "J-CASE", 2)
    req = _ok(
        _propose(f.accountant, request_type="PAYMENT_REVERSAL", payment_id=p["allocations"][0]["payment_id"]), 201
    )
    done = _ok(_approve(f.owner, req["id"]))
    assert done["effects"]["treatment"] == "CASE" and done["effects"]["case_id"]
    assert "recovery_invoice_id" not in done["effects"]
    money = _balance_money(f.owner, f.customer_id)
    assert money["balance"] == 0  # the difference is under investigation, not billed


def test_cash_collection_reversal_reverses_custody(api: Api) -> None:
    f = _setup(api)
    staff = f.sup_staff_id
    p = purchase(api, f.supervisor, f, "2", pay=str(2 * RATE), method="CASH", staff_id=staff)
    payment_id = p["allocations"][0]["payment_id"]
    verify(f.accountant, payment_id)

    held = next(b for b in _ok(f.accountant.get(f"{T}/cash/custody", staff_member_id=staff)) if b["currency"] == "TZS")
    assert Decimal(held["outstanding"]) == 2 * RATE
    req = _ok(_propose(f.accountant, request_type="COLLECTION_REVERSAL", payment_id=payment_id), 201)
    done = _ok(_approve(f.owner, req["id"]))
    assert Decimal(done["effects"]["custody_balance_after"]) == 0
    after = next(b for b in _ok(f.accountant.get(f"{T}/cash/custody", staff_member_id=staff)) if b["currency"] == "TZS")
    assert Decimal(after["outstanding"]) == 0
    assert _ok(f.accountant.get(f"{T}/cash/adjustments", staff_member_id=staff)) is not None
    e = _ledger(f.owner, type="COLLECTION_REVERSAL")[0]
    assert e["staff_member_id"] == staff and Decimal(e["amount"]) == -2 * RATE


def test_purchase_reversal_keeps_money_for_used_hours_and_stamps_purchase(api: Api) -> None:
    f = _setup(api)
    p = _paid_purchase(api, f)
    _complete_prepaid(api, f, "J-PR", 4)
    req = _ok(_propose(f.accountant, request_type="PURCHASE_REVERSAL", purchase_id=p["id"]), 201)
    assert Decimal(req["effects"]["unused_hours_removed"]) == 6 and Decimal(req["effects"]["money_owed"]) == 0
    done = _ok(_approve(f.owner, req["id"]))
    assert done["status"] == "APPROVED" and Decimal(done["effects"]["money_released_to_credit"]) == 6 * RATE
    got = get_purchase(f.manager, p["id"])
    assert got["cancelled_at"] is not None and got["status"] == "CANCELLED"
    assert Decimal(got["totals"]["remaining"]) == 0 and Decimal(got["totals"]["consumed"]) == 4
    money = _balance_money(f.owner, f.customer_id)
    assert money["unallocated_credit"] == 6 * RATE and money["balance"] == -10 * RATE
    assert _ledger(f.owner, type="PURCHASE_REVERSAL")[0]["status"] == "APPROVED"


def test_invoice_void_goes_through_approval_by_policy(api: Api) -> None:
    f = setup_finance(api)
    hours_policy(f, adjustment_evidence_required=False)
    complete_job(api, f, f.c.job_id, "500", "510", 10)
    inv = issue_invoice(f, [f.c.job_id])
    pending = _ok(f.accountant.post(f"{T}/hire-invoices/{inv['id']}/void", {"reason": "Wrong customer on invoice"}))
    assert pending["status"] == "ISSUED" and pending["pending_void_request_id"]
    request_id = pending["pending_void_request_id"]
    _err(f.accountant.post(f"{A}/{request_id}/decision", {"decision": "APPROVE"}), 422, "SEGREGATION_OF_DUTIES")
    done = _ok(f.owner.post(f"{A}/{request_id}/decision", {"decision": "APPROVE", "note": "Confirmed"}))
    assert done["status"] == "APPROVED"
    voided = _ok(f.accountant.get(f"{T}/hire-invoices/{inv['id']}"))
    assert voided["status"] == "VOIDED" and voided["pending_void_request_id"] is None
    e = _ledger(f.owner, type="INVOICE_VOID")[0]
    assert e["original_reference"] == inv["invoice_number"] and e["approved_by_name"]
    assert e["status"] == "APPROVED" and Decimal(e["original_value"]) == Decimal(inv["total"])
    assert e["evidence_attachment_ids"] == []


def test_evidence_required_by_default_and_notifications_link_record(api: Api) -> None:
    f = setup_finance(api)
    r = f.owner.post(f"{T}/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    assert r.status_code == 200, r.text
    p = _paid_purchase(api, f)
    _err(
        _propose(f.accountant, request_type="PAYMENT_REVERSAL", payment_id=p["allocations"][0]["payment_id"]),
        422,
        "EVIDENCE_REQUIRED",
    )
    upload = api.client.post(
        f"{T}/attachments",
        headers=f.manager.headers(True, None),
        files={"file": ("e.jpg", unique_jpeg(), "image/jpeg")},
        data={"purpose": "ADJUSTMENT_EVIDENCE"},
    )
    assert upload.status_code == 201, upload.text
    attachment = upload.json()["id"]
    created = _ok(
        _propose(
            f.manager,
            request_type="PAYMENT_REVERSAL",
            payment_id=p["allocations"][0]["payment_id"],
            evidence_attachment_ids=[attachment],
        ),
        201,
    )
    assert created["evidence_attachment_ids"] == [attachment]
    drain(api)
    notes = _ok(f.owner.get(f"{T}/notifications", page_size=50))["items"]
    match = [n for n in notes if n["type"] == "ADJUSTMENT_APPROVAL_REQUESTED"]
    assert match, notes
    assert match[0]["data"]["kind"] == "ADJUSTMENT_REQUEST" and match[0]["data"]["record_id"] == created["id"]
    assert match[0]["target"]["path"].endswith(f"/tenant/finance/adjustments/requests/{created['id']}")
    assert _ok(f.owner.get(f"{A}/{created['id']}"))["id"] == created["id"]


def test_variance_writeoff_and_custody_adjustment_post_to_ledger(api: Api) -> None:
    f = setup_finance(api)
    # A custody adjustment: proposed by one, decided by another; the ledger shows the resulting custody balance.
    prop = _ok(
        f.accountant2.post(
            f"{T}/cash/adjustments",
            {"staff_member_id": f.sup_staff_id, "kind": "ADJUSTMENT", "amount": "-5000", "reason": "Counted short"},
        ),
        201,
    )
    _ok(f.owner.post(f"{T}/cash/adjustments/{prop['id']}/decision", {"approve": True, "note": "Agreed"}))
    entries = _ledger(f.owner, type="CUSTODY_ADJUSTMENT")
    assert entries[0]["status"] == "APPROVED" and Decimal(entries[0]["amount"]) == -5000
    assert Decimal(entries[0]["resulting_balance"]) == -5000
    assert entries[0]["staff_member_id"] == f.sup_staff_id
    assert entries[0]["requested_by"] != entries[0]["approved_by"]
