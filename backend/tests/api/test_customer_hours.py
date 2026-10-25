"""Customer hours (accountability design A, controls 3.1): walk-ins, purchases priced only by the rate card and an
approved discount, claimed vs verified payments, activation only from verified money or authorised credit, the
append-only ledger with derived balances, work execution allocation with overrun handling, transfers,
cancellations, expiry and the tenant policy switches. Every rule is tenant configuration."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from asseta.core.db import get_sessionmaker
from asseta.modules.hours.expiry import run_hours_expiry
from tests.support.api import Api
from tests.support.finance import FinCtx, complete_job, setup_finance, tenant_sql
from tests.support.hours import RATE, balance, get_purchase, hours_policy, prepaid_job, purchase, verify
from tests.support.jobs import capture, unique_jpeg


def _setup(api: Api) -> FinCtx:
    f = setup_finance(api)
    r = f.owner.post(f"/api/v1/tenant/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    assert r.status_code == 200, r.text  # frees the machine for prepaid jobs
    return f


def _code(r: Any) -> str:
    return str(r.json()["error"]["code"])


def test_walk_in_cash_purchase_activates_only_after_independent_verification(api: Api) -> None:
    f = _setup(api)
    p = purchase(
        api,
        f.supervisor,
        f,
        "10",
        walk_in={"name": "Juma (site 4)", "phone": "+255700000001"},
        pay="850000",
        method="CASH",
    )
    assert p["purchase_number"] == "HP-2026-00001"
    assert p["customer_kind"] == "WALK_IN" and p["status"] == "AWAITING_PAYMENT"
    assert Decimal(p["amount"]) == 10 * RATE and Decimal(p["hourly_rate"]) == RATE
    assert p["payment"]["status"] == "CLAIMED" and p["payment"]["method"] == "CASH"
    assert Decimal(p["totals"]["activated"]) == 0 and Decimal(p["totals"]["amount_claimed_unverified"]) == 10 * RATE
    walk_in = f.owner.get(f"/api/v1/tenant/customers/{p['customer_id']}").json()
    assert walk_in["code"] == "WALK-00001" and walk_in["kind"] == "WALK_IN"

    # Evidence never verifies: a receipt photo is stored, the payment stays CLAIMED.
    up = api.client.post(
        "/api/v1/tenant/payment-evidence",
        headers=f.supervisor.headers(True, None),
        files={"file": ("r.jpg", unique_jpeg(), "image/jpeg")},
    )
    assert up.status_code == 201, up.text
    pay_id = p["payment"]["id"]
    ev = f.supervisor.post(f"/api/v1/tenant/customer-payments/{pay_id}/evidence", {"attachment_ids": [up.json()["id"]]})
    assert ev.status_code == 201 and len(ev.json()) == 1, ev.text
    assert get_purchase(f.owner, p["id"])["status"] == "AWAITING_PAYMENT"

    # The recorder cannot verify; an accountant can, and only then do the hours activate.
    mine = f.supervisor.post(f"/api/v1/tenant/customer-payments/{pay_id}/decision", {"verified": True})
    assert mine.status_code == 403
    verify(f.accountant2, pay_id)
    after = get_purchase(f.owner, p["id"])
    assert after["status"] == "ACTIVE" and Decimal(after["totals"]["activated_from_payments"]) == 10
    b = balance(f.owner, p["customer_id"], f.c.t.machine_id)
    assert b is not None and Decimal(b["remaining"]) == 10
    ledger = f.owner.get("/api/v1/tenant/hours-ledger", purchase_id=p["id"]).json()
    assert [e["entry_type"] for e in ledger["items"]] == ["ACTIVATED"]
    assert ledger["items"][0]["payment_id"] == pay_id
    assert ledger["items"][0]["purchase_number"] == p["purchase_number"]  # names, not ids
    assert ledger["items"][0]["job_id"] is None and ledger["items"][0]["job_number"] is None

    # Upgrade the walk-in later (audited); history stays on the same customer.
    reg = f.owner.post(
        f"/api/v1/tenant/customers/{p['customer_id']}/registration", {"code": "JUMA", "name": "Juma Ltd"}
    )
    assert reg.status_code == 200 and reg.json()["kind"] == "REGISTERED", reg.text
    listed = f.owner.get("/api/v1/tenant/hours-purchases", q="Juma").json()
    assert listed["total"] == 1


def test_partial_payment_activates_pro_rata_and_policy_can_require_full_payment(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "10", pay=str(3 * RATE + 1000))
    verify(f.accountant2, p["payment"]["id"])
    got = get_purchase(f.owner, p["id"])
    assert got["status"] == "PARTLY_ACTIVE" and Decimal(got["totals"]["activated"]) == Decimal("3.01")
    assert Decimal(got["totals"]["awaiting_activation"]) == Decimal("6.99")

    hours_policy(f, partial_activation=False)
    q = purchase(api, f.accountant, f, "4", pay=str(2 * RATE))
    verify(f.accountant2, q["payment"]["id"])
    assert Decimal(get_purchase(f.owner, q["id"])["totals"]["activated"]) == 0
    rest = f.accountant.post(
        "/api/v1/tenant/customer-payments",
        {
            "customer_id": f.customer_id,
            "amount": str(2 * RATE),
            "method": "BANK",
            "reference": "TRX-9",
            "received_at": api.clock.now.isoformat(),
        },
    )
    assert rest.status_code == 201, rest.text
    link = f.manager.post(
        f"/api/v1/tenant/hours-purchases/{q['id']}/allocations",
        {"payment_id": rest.json()["id"], "amount": str(2 * RATE)},
    )
    assert link.status_code == 200, link.text
    over = f.manager.post(
        f"/api/v1/tenant/hours-purchases/{q['id']}/allocations", {"payment_id": rest.json()["id"], "amount": "1"}
    )
    assert over.status_code == 422 and _code(over) == "OVER_ALLOCATION"
    verify(f.accountant2, rest.json()["id"])
    assert get_purchase(f.owner, q["id"])["status"] == "ACTIVE"


def test_discount_needs_a_second_person_and_applies_automatically(api: Api) -> None:
    f = _setup(api)
    body = {"customer_id": f.customer_id, "percent": "10", "effective_from": "2026-01-01", "reason": "Volume customer"}
    d = f.manager.post("/api/v1/tenant/customer-discounts", body)
    assert d.status_code == 201 and d.json()["status"] == "PROPOSED", d.text
    did = d.json()["id"]
    # Not yet approved: the standard rate applies.
    assert Decimal(purchase(api, f.manager, f, "1")["discount_percent"]) == 0
    own = f.manager.post(f"/api/v1/tenant/customer-discounts/{did}/decision", {"approve": True})
    assert own.status_code == 422 and _code(own) == "SEGREGATION_OF_DUTIES"
    ok = f.owner.post(f"/api/v1/tenant/customer-discounts/{did}/decision", {"approve": True, "note": "Agreed"})
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED", ok.text
    p = purchase(api, f.manager, f, "10")
    assert Decimal(p["discount_percent"]) == 10 and p["discount_id"] == did
    assert Decimal(p["amount"]) == Decimal(10 * RATE) * Decimal("0.9")
    # Approved terms are frozen: editing is refused; revocation stops it applying.
    frozen = f.manager.put(
        f"/api/v1/tenant/customer-discounts/{did}", {**body, "percent": "50", "version": ok.json()["version"]}
    )
    assert frozen.status_code == 409 and _code(frozen) == "NOT_PROPOSED"
    rv = f.owner.post(f"/api/v1/tenant/customer-discounts/{did}/revoke", {"reason": "Contract ended"})
    assert rv.status_code == 200 and rv.json()["status"] == "REVOKED"
    assert Decimal(purchase(api, f.manager, f, "1")["discount_percent"]) == 0
    listed = f.owner.get("/api/v1/tenant/customer-discounts", customer_id=f.customer_id).json()
    assert listed["total"] == 1


def test_credit_activation_within_an_approved_limit_and_payments_settle_it(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.manager, f, "10")
    none = f.accountant.post(
        f"/api/v1/tenant/hours-purchases/{p['id']}/credit-activations", {"hours": "2", "reason": "Trusted"}
    )
    assert none.status_code == 422 and _code(none) == "NO_CREDIT_ARRANGEMENT"
    c = f.manager.post(
        "/api/v1/tenant/credit-arrangements",
        {
            "customer_id": f.customer_id,
            "limit_amount": str(5 * RATE),
            "effective_from": "2026-01-01",
            "reason": "Monthly account",
        },
    )
    assert c.status_code == 201, c.text
    assert (
        f.manager.post(f"/api/v1/tenant/credit-arrangements/{c.json()['id']}/decision", {"approve": True}).status_code
        == 422
    )
    assert (
        f.owner.post(f"/api/v1/tenant/credit-arrangements/{c.json()['id']}/decision", {"approve": True}).status_code
        == 200
    )
    ok = f.accountant.post(
        f"/api/v1/tenant/hours-purchases/{p['id']}/credit-activations", {"hours": "4", "reason": "Urgent work"}
    )
    assert ok.status_code == 200, ok.text
    assert Decimal(ok.json()["totals"]["activated_on_credit"]) == 4 and ok.json()["status"] == "PARTLY_ACTIVE"
    too_much = f.accountant.post(
        f"/api/v1/tenant/hours-purchases/{p['id']}/credit-activations", {"hours": "2", "reason": "More"}
    )
    assert too_much.status_code == 422 and _code(too_much) == "CREDIT_LIMIT_EXCEEDED"
    exposure = f.owner.get(f"/api/v1/tenant/customers/{f.customer_id}/credit-exposure").json()
    assert Decimal(exposure["exposure"]) == 4 * RATE and Decimal(exposure["available"]) == RATE
    # A verified payment for 4 hours settles the credit (no extra hours); paying the rest activates the rest.
    pay = f.accountant.post(
        "/api/v1/tenant/customer-payments",
        {
            "customer_id": f.customer_id,
            "amount": str(10 * RATE),
            "method": "BANK",
            "reference": "B-1",
            "received_at": api.clock.now.isoformat(),
        },
    ).json()
    f.manager.post(
        f"/api/v1/tenant/hours-purchases/{p['id']}/allocations", {"payment_id": pay["id"], "amount": str(4 * RATE)}
    )
    verify(f.accountant2, pay["id"])
    got = get_purchase(f.owner, p["id"])
    assert Decimal(got["totals"]["activated"]) == 4
    assert Decimal(f.owner.get(f"/api/v1/tenant/customers/{f.customer_id}/credit-exposure").json()["exposure"]) == 0
    f.manager.post(
        f"/api/v1/tenant/hours-purchases/{p['id']}/allocations", {"payment_id": pay["id"], "amount": str(6 * RATE)}
    )
    assert get_purchase(f.owner, p["id"])["status"] == "ACTIVE"
    # A payment is never allocated twice: invoices see what purchases already took.
    bal = f.owner.get(f"/api/v1/tenant/customers/{f.customer_id}/balance").json()[0]
    assert Decimal(bal["unallocated_credit"]) == 0


def test_prepaid_job_start_gate_work_execution_allocation_and_overrun(api: Api) -> None:
    f = _setup(api)
    job = prepaid_job(api, f, "P-1")
    t0 = api.clock.now
    r = f.owner.post("/api/v1/tenant/meter-captures", capture(job, "OPENING", "1000", t0, mode="MANUAL"))
    assert r.status_code == 201, r.text
    blocked = f.owner.post(f"/api/v1/tenant/jobs/{job}/transitions", {"action": "START"})
    assert blocked.status_code == 422 and _code(blocked) == "NO_AVAILABLE_HOURS"
    first = purchase(api, f.accountant, f, "4", pay=str(4 * RATE))
    second = purchase(api, f.accountant, f, "3", pay=str(3 * RATE))
    for p in (first, second):
        verify(f.accountant2, p["payment"]["id"])
    # Start, work 10 h, close, acknowledge, complete.
    assert f.owner.post(f"/api/v1/tenant/jobs/{job}/transitions", {"action": "START"}).status_code == 200
    t1 = t0 + timedelta(hours=10)
    api.clock.set_at(t1)
    assert (
        f.owner.post("/api/v1/tenant/meter-captures", capture(job, "CLOSING", "1010", t1, mode="MANUAL")).status_code
        == 201
    )
    ack = f.owner.post(
        f"/api/v1/tenant/jobs/{job}/acknowledgements",
        {
            "client_id": first["id"],
            "method": "NAME_CONFIRMATION",
            "signer_name": "Engineer",
            "captured_at": t1.isoformat(),
        },
    )
    assert ack.status_code == 201, ack.text
    done = f.owner.post(f"/api/v1/tenant/jobs/{job}/transitions", {"action": "COMPLETE"})
    assert done.status_code == 200, done.text

    wea = f.owner.get("/api/v1/tenant/work-execution-allocations", job_id=job).json()["items"][0]
    assert Decimal(wea["billable_hours"]) == 10 and Decimal(wea["consumed_hours"]) == 7
    assert Decimal(wea["overrun_hours"]) == 3 and wea["exception_status"] == "OPEN"
    assert [(line["purchase_number"], Decimal(line["hours"])) for line in wea["lines"]] == [
        (first["purchase_number"], Decimal(4)),
        (second["purchase_number"], Decimal(3)),
    ]  # FIFO: the oldest purchase first
    used = f.owner.get("/api/v1/tenant/hours-ledger", job_id=job).json()["items"]
    job_number = f.owner.get(f"/api/v1/tenant/jobs/{job}").json()["job"]["job_number"]
    assert used and {(e["purchase_number"], e["job_number"]) for e in used} == {
        (first["purchase_number"], job_number),
        (second["purchase_number"], job_number),
    }
    assert get_purchase(f.owner, first["id"])["status"] == "CONSUMED"
    summary = f.owner.get(f"/api/v1/tenant/jobs/{job}").json()
    assert summary["blocking_exceptions"] == 1 and summary["billing_ready"] is False
    # Prepaid work is never invoiced again.
    inv = f.accountant.post("/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": [job]})
    assert inv.status_code == 422 and _code(inv) == "JOB_PREPAID_HOURS"

    # New verified hours on that machine cover the overrun first and clear the exception.
    top_up = purchase(api, f.accountant, f, "5", pay=str(5 * RATE))
    verify(f.accountant2, top_up["payment"]["id"])
    wea = f.owner.get(f"/api/v1/tenant/work-execution-allocations/{wea['id']}").json()
    assert Decimal(wea["overrun_hours"]) == 0 and wea["exception_status"] == "EXPLAINED"
    b = balance(f.owner, f.customer_id, f.c.t.machine_id)
    assert b is not None and Decimal(b["remaining"]) == 2 and Decimal(b["consumed"]) == 10
    entries = tenant_sql(f.tid, "SELECT entry_type, count(*) FROM hours_ledger_entry GROUP BY entry_type ORDER BY 1")
    assert dict(entries) == {"ACTIVATED": 3, "CONSUMED": 3}


def test_transfer_to_another_machine_needs_approval_and_keeps_history(api: Api) -> None:
    f = _setup(api)
    other = f.owner.post("/api/v1/tenant/machines", {"asset_code": "EXC-900", "name": "Backup excavator"}).json()["id"]
    p = purchase(api, f.accountant, f, "6", pay=str(6 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    too_many = f.supervisor.post(
        "/api/v1/tenant/hours-transfers",
        {"purchase_id": p["id"], "to_machine_id": other, "hours": "7", "reason": "Breakdown"},
    )
    assert too_many.status_code == 422 and _code(too_many) == "EXCEEDS_REMAINING_HOURS"
    t = f.supervisor.post(
        "/api/v1/tenant/hours-transfers",
        {"purchase_id": p["id"], "to_machine_id": other, "hours": "4", "reason": "Breakdown"},
    )
    assert t.status_code == 201 and t.json()["status"] == "PENDING", t.text
    assert balance(f.owner, f.customer_id, other) is None  # nothing moves before approval
    ok = f.manager.post(f"/api/v1/tenant/hours-transfers/{t.json()['id']}/decision", {"approve": True})
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED", ok.text
    got = get_purchase(f.owner, p["id"])
    assert got["machine_id"] == f.c.t.machine_id  # the original assignment stays visible
    machines = {m["machine_id"]: Decimal(m["remaining"]) for m in got["machines"]}
    assert machines == {f.c.t.machine_id: 2, other: 4}
    on_other = f.owner.get(f"/api/v1/tenant/machines/{other}/hours-balances").json()
    assert Decimal(on_other[0]["remaining"]) == 4 and Decimal(on_other[0]["transferred_in"]) == 4
    history = f.owner.get("/api/v1/tenant/hours-transfers", purchase_id=p["id"]).json()
    assert history["total"] == 1

    # Self-approval is refused even for someone holding the approval permission.
    t2 = f.manager.post(
        "/api/v1/tenant/hours-transfers",
        {"purchase_id": p["id"], "to_machine_id": other, "hours": "1", "reason": "Again"},
    )
    mine = f.manager.post(f"/api/v1/tenant/hours-transfers/{t2.json()['id']}/decision", {"approve": True})
    assert mine.status_code == 422 and _code(mine) == "SEGREGATION_OF_DUTIES"
    wd = f.manager.post(f"/api/v1/tenant/hours-transfers/{t2.json()['id']}/withdraw", {"reason": "Not needed"})
    assert wd.status_code == 200 and wd.json()["status"] == "WITHDRAWN"


def test_cancellation_reverses_unused_hours_and_returns_money_to_credit(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "5", pay=str(5 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    req = f.manager.post(f"/api/v1/tenant/hours-purchases/{p['id']}/cancellation", {"reason": "Customer changed plans"})
    assert req.status_code == 201 and req.json()["status"] == "PENDING", req.text
    dup = f.manager.post(f"/api/v1/tenant/hours-purchases/{p['id']}/cancellation", {"reason": "Again please"})
    assert dup.status_code == 409 and _code(dup) == "CANCELLATION_PENDING"
    assert get_purchase(f.owner, p["id"])["status"] == "ACTIVE"
    ok = f.owner.post(f"/api/v1/tenant/hours-cancellations/{req.json()['id']}/decision", {"approve": True})
    assert ok.status_code == 200, ok.text
    got = get_purchase(f.owner, p["id"])
    assert got["status"] == "CANCELLED" and Decimal(got["totals"]["reversed"]) == 5
    assert Decimal(got["totals"]["remaining"]) == 0 and got["allocations"][0]["released_at"] is not None
    bal = f.owner.get(f"/api/v1/tenant/customers/{f.customer_id}/balance").json()[0]
    assert Decimal(bal["unallocated_credit"]) == 5 * RATE

    # Policy without approval: applied at once; a used purchase cannot be cancelled by default.
    hours_policy(f, cancellation_requires_approval=False)
    q = purchase(api, f.accountant, f, "1", pay=str(RATE))
    direct = f.manager.post(f"/api/v1/tenant/hours-purchases/{q['id']}/cancellation", {"reason": "Wrong machine"})
    assert direct.status_code == 201 and direct.json()["status"] == "APPROVED"
    assert get_purchase(f.owner, q["id"])["status"] == "CANCELLED"


def test_expiry_sweep_warns_then_expires_unused_hours_once(api: Api) -> None:
    f = _setup(api)
    hours_policy(f, expiry_days=10, expiry_warning_days=3)
    p = purchase(api, f.accountant, f, "8", pay=str(8 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    start = api.clock.now
    run_hours_expiry(get_sessionmaker(), start + timedelta(days=2))
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["expired"]) == 0
    warned = run_hours_expiry(get_sessionmaker(), start + timedelta(days=8))
    assert warned.expired_entries == 0
    first = run_hours_expiry(get_sessionmaker(), start + timedelta(days=11))
    again = run_hours_expiry(get_sessionmaker(), start + timedelta(days=12))
    assert first.expired_entries == 1 and again.expired_entries == 0
    assert warned.failures == first.failures == again.failures == 0
    got = get_purchase(f.owner, p["id"])
    assert got["status"] == "EXPIRED" and Decimal(got["totals"]["expired"]) == 8
    assert Decimal(got["totals"]["remaining"]) == 0


def test_switched_off_tenant_keeps_the_invoice_flow(api: Api) -> None:
    f = _setup(api)
    hours_policy(f, enabled=False)
    body = {"customer_id": f.customer_id, "machine_id": f.c.t.machine_id, "hours": "2"}
    r = f.manager.post("/api/v1/tenant/hours-purchases", body)
    assert r.status_code == 422 and _code(r) == "HOURS_DISABLED"
    job = f.owner.post(
        "/api/v1/tenant/jobs",
        {
            "contract_id": f.c.contract_id,
            "job_number": "I-1",
            "machine_id": f.c.t.machine_id,
            "planned_start": api.clock.now.isoformat(),
        },
    )
    assert job.status_code == 201 and job.json()["billing_mode"] == "INVOICE"
    refused = f.owner.post(
        "/api/v1/tenant/jobs",
        {
            "contract_id": f.c.contract_id,
            "job_number": "I-2",
            "machine_id": f.c.t.machine_id,
            "planned_start": api.clock.now.isoformat(),
            "billing_mode": "PREPAID_HOURS",
        },
    )
    assert refused.status_code == 422 and _code(refused) == "HOURS_DISABLED"
    for action in ("SUBMIT", "APPROVE"):
        assert (
            f.owner.post(f"/api/v1/tenant/jobs/{job.json()['id']}/transitions", {"action": action}).status_code == 200
        )
    summary = complete_job(api, f, job.json()["id"], "500", "506", 6)
    assert summary["billing_ready"] is True
    assert f.owner.get("/api/v1/tenant/work-execution-allocations").json()["total"] == 0


def test_reason_lists_are_tenant_data_and_policy_can_require_them(api: Api) -> None:
    f = _setup(api)
    rc = f.owner.post("/api/v1/tenant/hours-reason-codes", {"kind": "DISCOUNT", "code": "VOL", "label": "Volume"})
    assert rc.status_code == 201, rc.text
    dup = f.owner.post("/api/v1/tenant/hours-reason-codes", {"kind": "DISCOUNT", "code": "VOL", "label": "Again"})
    assert dup.status_code == 409
    hours_policy(f, reason_code_required=True)
    body: dict[str, Any] = {
        "customer_id": f.customer_id,
        "percent": "5",
        "effective_from": "2026-01-01",
        "reason": "Loyal",
    }
    missing = f.manager.post("/api/v1/tenant/customer-discounts", body)
    assert missing.status_code == 422 and _code(missing) == "REASON_CODE_REQUIRED"
    ok = f.manager.post("/api/v1/tenant/customer-discounts", {**body, "reason_code_id": rc.json()["id"]})
    assert ok.status_code == 201, ok.text
    off = f.owner.post(f"/api/v1/tenant/hours-reason-codes/{rc.json()['id']}/deactivate", {"reason": "Retired code"})
    assert off.status_code == 200 and off.json()["is_active"] is False
    stale = f.manager.post("/api/v1/tenant/customer-discounts", {**body, "reason_code_id": rc.json()["id"]})
    assert stale.status_code == 422 and _code(stale) == "REASON_CODE_INACTIVE"
    assert f.owner.get("/api/v1/tenant/hours-reason-codes").json()["total"] == 0
    assert f.owner.get("/api/v1/tenant/hours-reason-codes", include_inactive=True).json()["total"] == 1


def test_ledger_and_purchases_are_immutable_in_the_database(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "2", pay=str(2 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    for stmt in (
        "UPDATE hours_ledger_entry SET hours = 99",
        "DELETE FROM hours_ledger_entry",
        "UPDATE hours_purchase SET hours = 99",
        "DELETE FROM hours_purchase",
    ):
        with pytest.raises(DBAPIError):
            tenant_sql(f.tid, stmt)
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["remaining"]) == 2


def test_offline_walk_in_purchase_is_applied_exactly_once(api: Api) -> None:
    f = _setup(api)
    device = "android-hours-0001"
    h = {**f.supervisor.headers(True, None), "X-Device-Id": device}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": device, "platform": "ANDROID", "app_version": "1.2.0"}
    )
    assert reg.status_code == 201, reg.text
    op = {
        "id": "6b1f7a52-2d5a-4f43-9d7e-0c9a3b0e0001",
        "op_type": "HOURS_PURCHASE",
        "created_at_device": api.clock.now.isoformat(),
        "payload": {
            "walk_in": {"name": "Roadside customer"},
            "machine_id": f.c.t.machine_id,
            "hours": "3",
            "payment": {"method": "CASH", "received_at": api.clock.now.isoformat()},
        },
    }
    for expected in ("ACKED", "DUPLICATE"):
        r = api.client.post(
            "/api/v1/sync/push", headers=h, json={"device_now": api.clock.now.isoformat(), "operations": [op]}
        )
        assert r.status_code == 200 and r.json()["results"][0]["status"] == expected, r.text
    counts = tenant_sql(
        f.tid,
        "SELECT (SELECT count(*) FROM hours_purchase), (SELECT count(*) FROM customer_payment),"
        " (SELECT count(*) FROM customer WHERE kind = 'WALK_IN')",
    )[0]
    assert tuple(counts) == (1, 1, 1)
    p = f.owner.get("/api/v1/tenant/hours-purchases").json()["items"][0]
    assert p["source"] == "SYNC" and p["status"] == "AWAITING_PAYMENT"  # offline never bypasses verification
