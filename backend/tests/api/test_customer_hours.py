"""Customer hours (accountability design A, controls 3.1): walk-ins, purchases priced only by the rate card and an
approved discount, claimed vs verified payments, activation only from verified money or authorised credit, the
append-only ledger with derived balances, consumption by approved machine reports (oldest order first), transfers,
cancellations, expiry and the tenant policy switches. Every rule is tenant configuration."""

import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from asseta.core.db import get_sessionmaker
from asseta.modules.hours.expiry import run_hours_expiry
from tests.support.api import Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.hours import RATE, balance, get_purchase, hours_policy, purchase, verify
from tests.support.machine_reports import baseline, cust, idle, later, ok, report_body, submit
from tests.support.meter import unique_jpeg


def _setup(api: Api) -> FinCtx:
    return setup_finance(api)


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
    assert ledger["items"][0]["machine_report_id"] is None and ledger["items"][0]["machine_report_number"] is None

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
    q = f.supervisor.get(
        "/api/v1/tenant/hours-purchases/quote", machine_id=f.c.t.machine_id, customer_id=f.customer_id, hours="10"
    )
    assert q.status_code == 200, q.text
    p = purchase(api, f.manager, f, "10")
    assert Decimal(p["discount_percent"]) == 10 and p["discount_id"] == did
    assert Decimal(p["amount"]) == Decimal(10 * RATE) * Decimal("0.9")
    # The quote the seller saw before saving is exactly what the sale charged.
    assert Decimal(q.json()["amount"]) == Decimal(p["amount"]) and Decimal(q.json()["discount_percent"]) == 10
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


def test_approved_machine_report_consumes_the_oldest_purchase_first(api: Api) -> None:
    f = _setup(api)
    m = f.c.t.machine_id
    baseline(api, f, m)
    # No verified hours yet: a report may not give the customer hours they do not have.
    at = later(api, 7)
    r = f.supervisor.post("/api/v1/tenant/machine-reports", report_body(m, "1007", at, [cust(f.customer_id, 7)]))
    assert r.status_code == 422 and _code(r) == "HOURS_NOT_AVAILABLE", r.text
    first = purchase(api, f.accountant, f, "4", pay=str(4 * RATE))
    second = purchase(api, f.accountant, f, "3", pay=str(3 * RATE))
    for p in (first, second):
        verify(f.accountant2, p["payment"]["id"])
    rep = submit(f.supervisor, report_body(m, "1007", at, [cust(f.customer_id, 7)]))
    done = ok(f.manager.post(f"/api/v1/tenant/machine-reports/{rep['id']}/approve", {}))
    assert [(lot["purchase_number"], Decimal(lot["hours"])) for lot in done["lines"][0]["lots"]] == [
        (first["purchase_number"], Decimal(4)),
        (second["purchase_number"], Decimal(3)),
    ]  # FIFO: the oldest purchase first
    used = f.owner.get("/api/v1/tenant/hours-ledger", machine_report_id=rep["id"]).json()["items"]
    assert used and {(e["purchase_number"], e["machine_report_number"]) for e in used} == {
        (first["purchase_number"], rep["report_number"]),
        (second["purchase_number"], rep["report_number"]),
    }
    assert get_purchase(f.owner, first["id"])["status"] == "CONSUMED"
    b = balance(f.owner, f.customer_id, m)
    assert b is not None and Decimal(b["remaining"]) == 0 and Decimal(b["consumed"]) == 7
    entries = tenant_sql(f.tid, "SELECT entry_type, count(*) FROM hours_ledger_entry GROUP BY entry_type ORDER BY 1")
    assert dict(entries) == {"ACTIVATED": 2, "CONSUMED": 2}


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


def test_switched_off_tenant_sells_no_hours_and_reports_only_non_productive_time(api: Api) -> None:
    f = _setup(api)
    m = f.c.t.machine_id
    baseline(api, f, m)
    hours_policy(f, enabled=False)
    body = {"customer_id": f.customer_id, "machine_id": m, "hours": "2"}
    r = f.manager.post("/api/v1/tenant/hours-purchases", body)
    assert r.status_code == 422 and _code(r) == "HOURS_DISABLED"
    at = later(api, 3)
    r = f.supervisor.post("/api/v1/tenant/machine-reports", report_body(m, "1003", at, [cust(f.customer_id, 3)]))
    assert r.status_code == 422 and _code(r) == "HOURS_DISABLED", r.text
    reasons = {x["code"]: x["id"] for x in ok(f.owner.get("/api/v1/tenant/machine-report-reasons"))}
    rep = submit(f.supervisor, report_body(m, "1003", at, [idle(reasons["BREAKDOWN"], 3)]))
    assert ok(f.manager.post(f"/api/v1/tenant/machine-reports/{rep['id']}/approve", {}))["status"] == "APPROVED"


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


def test_hours_quote_and_offline_prices_match_the_sale(api: Api) -> None:
    f = _setup(api)
    walk = f.supervisor.get("/api/v1/tenant/hours-purchases/quote", machine_id=f.c.t.machine_id, hours="6")
    assert walk.status_code == 200, walk.text
    assert Decimal(walk.json()["amount"]) == Decimal(6 * RATE) and Decimal(walk.json()["discount_percent"]) == 0
    sold = purchase(api, f.supervisor, f, "6", walk_in={"name": "Roadside customer"}, pay=str(6 * RATE), method="CASH")
    assert Decimal(sold["amount"]) == Decimal(walk.json()["amount"])
    bad = f.supervisor.get("/api/v1/tenant/hours-purchases/quote", machine_id=f.c.t.machine_id, hours="0")
    assert bad.status_code == 422
    # The phone's download carries the machine's current rate, so it can show the total offline.
    device = "android-hours-price"
    h = {**f.supervisor.headers(True, None), "X-Device-Id": device}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": device, "platform": "ANDROID", "app_version": "1.2.0"}
    )
    assert reg.status_code == 201, reg.text
    boot = api.client.get("/api/v1/sync/bootstrap", headers=h).json()
    assert "SYNC_HOURS_PRICES" in boot["capabilities"]
    prices = {p["machine_id"]: Decimal(p["hourly_rate"]) for p in boot["data"]["hours_prices"]}
    assert prices.get(f.c.t.machine_id) == Decimal(RATE)


def test_split_payment_cash_bank_and_mobile_money(api: Api) -> None:
    f = _setup(api)
    now = api.clock.now.isoformat()
    total = 6 * RATE
    cash, bank = Decimal(total) * Decimal("0.35"), Decimal(total) * Decimal("0.5")
    mobile = Decimal(total) - cash - bank
    parts = [
        {"method": "CASH", "amount": str(cash), "received_at": now},
        {"method": "BANK", "amount": str(bank), "reference": "CRDB-1", "received_at": now},
        {"method": "MOBILE_MONEY", "amount": str(mobile), "reference": "MPESA-1", "received_at": now},
    ]
    body = {"customer_id": f.customer_id, "machine_id": f.c.t.machine_id, "hours": "6"}
    # Field staff record only cash unless the company switches non-cash on.
    refused = f.supervisor.post("/api/v1/tenant/hours-purchases", {**body, "payments": parts})
    assert refused.status_code == 403 and _code(refused) == "PAYMENT_NOT_PERMITTED", refused.text
    over = [*parts, {"method": "CASH", "amount": "1", "received_at": now}]
    too_much = f.owner.post("/api/v1/tenant/hours-purchases", {**body, "payments": over})
    assert too_much.status_code == 422 and _code(too_much) == "PAYMENTS_EXCEED_TOTAL", too_much.text
    no_amount = f.owner.post(
        "/api/v1/tenant/hours-purchases", {**body, "payments": [{**parts[0], "amount": None}, parts[1]]}
    )
    assert no_amount.status_code == 422, no_amount.text

    hours_policy(f, field_noncash_payments=True)
    r = f.supervisor.post("/api/v1/tenant/hours-purchases", {**body, "payments": parts})
    assert r.status_code == 201, r.text
    p = r.json()
    assert [x["method"] for x in p["payments"]] == ["CASH", "BANK", "MOBILE_MONEY"]
    assert sum(Decimal(x["amount"]) for x in p["payments"]) == Decimal(p["amount"]) == Decimal(total)
    assert p["status"] == "AWAITING_PAYMENT"  # every part is only claimed until the office verifies it
    # The office verifies the bank part: half the bill, so half the hours become usable (partial activation).
    verify(f.accountant, p["payments"][1]["id"])
    assert get_purchase(f.owner, p["id"])["status"] == "PARTLY_ACTIVE"
    for part in (p["payments"][0], p["payments"][2]):
        verify(f.accountant, part["id"])
    assert get_purchase(f.owner, p["id"])["status"] == "ACTIVE"


def test_offline_split_payment_parts_carry_their_own_evidence(api: Api) -> None:
    f = _setup(api)
    hours_policy(f, field_noncash_payments=True)
    device = "android-hours-split"
    h = {**f.supervisor.headers(True, None), "X-Device-Id": device}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": device, "platform": "ANDROID", "app_version": "1.2.0"}
    )
    assert reg.status_code == 201, reg.text
    slip = unique_jpeg()
    up = api.client.post(
        "/api/v1/sync/blobs",
        headers=h,
        json={"sha256": hashlib.sha256(slip).hexdigest(), "size_bytes": len(slip), "purpose": "PAYMENT_EVIDENCE"},
    ).json()
    api.client.put(f"/api/v1/sync/blobs/{up['id']}/chunks/0", headers=h, content=slip)
    done = api.client.post(f"/api/v1/sync/blobs/{up['id']}/complete", headers=h).json()
    now = api.clock.now.isoformat()
    op = {
        "id": str(uuid.uuid4()),
        "op_type": "HOURS_PURCHASE",
        "created_at_device": now,
        "payload": {
            "walk_in": {"name": "Split payer"},
            "machine_id": f.c.t.machine_id,
            "hours": "2",
            "payments": [
                {"method": "CASH", "amount": str(RATE), "received_at": now},
                {
                    "method": "BANK",
                    "amount": str(RATE),
                    "reference": "CRDB-77",
                    "received_at": now,
                    "evidence_upload_ids": [up["id"]],
                },
            ],
        },
    }
    for expected in ("ACKED", "DUPLICATE"):
        r = api.client.post("/api/v1/sync/push", headers=h, json={"device_now": now, "operations": [op]})
        assert r.status_code == 200 and r.json()["results"][0]["status"] == expected, r.text
    pays = f.accountant.get("/api/v1/tenant/customer-payments").json()["items"]
    bank = next(p for p in pays if p["method"] == "BANK")
    ev = f.accountant.get(f"/api/v1/tenant/customer-payments/{bank['id']}/evidence")
    assert ev.status_code == 200 and [e["attachment_id"] for e in ev.json()] == [done["attachment_id"]], ev.text
    assert sorted(p["method"] for p in pays) == ["BANK", "CASH"]  # exactly one of each, even after the retry


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
