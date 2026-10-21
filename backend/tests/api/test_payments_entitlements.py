"""Gate 1: manual platform payments (record/verify), idempotency, credits, and grace/past-due/suspension/
reactivation driven by the versioned entitlement policy; tenant data is never deleted or hidden."""

import uuid
from datetime import date
from typing import Any

from tests.support.api import Api

NOV1 = date(2026, 11, 1)


def _billed_tenant(api: Api, name: str, price: str = "100000") -> tuple[dict[str, Any], dict[str, Any]]:
    t = api.onboard(name, price=price, terms_days=14)
    api.activate(t)
    api.add_machines(t["owner"], 1, enroll_on=NOV1)
    inv = api.generate(t["subscription_id"], NOV1)["created"][0]
    return t, inv


def _pay(api: Api, inv: dict[str, Any], amount: str, ref: str, key: str | None = None) -> Any:
    return api.platform.post(
        "/api/v1/platform/payments",
        {
            "invoice_id": inv["id"],
            "amount": amount,
            "currency": "TZS",
            "method": "MOBILE_MONEY",
            "reference": ref,
            "received_on": "2026-11-03",
        },
        key=key,
    )


def test_payment_record_verify_partial_and_full(api: Api) -> None:
    _, inv = _billed_tenant(api, "Pay Co")
    key = str(uuid.uuid4())
    p1 = _pay(api, inv, "40000", "MPESA-QX1", key=key)
    assert p1.status_code == 201 and p1.json()["status"] == "RECORDED"
    replay = _pay(api, inv, "40000", "MPESA-QX1", key=key)  # client retry with same key -> same result
    assert replay.status_code == 201 and replay.json()["id"] == p1.json()["id"]
    misuse = _pay(api, inv, "1", "OTHER", key=key)
    assert misuse.status_code == 409 and misuse.json()["error"]["code"] == "IDEMPOTENCY_MISMATCH"
    dup = _pay(api, inv, "40000", "MPESA-QX1")  # new key, same provider reference
    assert dup.json()["error"]["code"] == "DUPLICATE_PAYMENT_REFERENCE"
    assert (
        api.platform.post(
            "/api/v1/platform/payments",
            {
                **{
                    "invoice_id": inv["id"],
                    "amount": "40000",
                    "currency": "TZS",
                    "method": "MOBILE_MONEY",
                    "reference": "NO-KEY",
                    "received_on": "2026-11-03",
                }
            },
        ).status_code
        == 201
    )  # helper always adds a key
    # Recorded (unverified) payments do not reduce the balance.
    assert api.platform.get(f"/api/v1/platform/invoices/{inv['id']}").json()["balance"] == "100000.0000"
    v = api.platform.post(
        f"/api/v1/platform/payments/{p1.json()['id']}/decision", {"verified": True, "note": "Matched M-Pesa statement"}
    )
    assert v.json()["status"] == "VERIFIED"
    after = api.platform.get(f"/api/v1/platform/invoices/{inv['id']}").json()
    assert (after["amount_paid"], after["balance"], after["status"]) == ("40000.0000", "60000.0000", "PARTIALLY_PAID")
    again = api.platform.post(
        f"/api/v1/platform/payments/{p1.json()['id']}/decision", {"verified": False, "note": "flip"}
    )
    assert again.json()["error"]["code"] == "PAYMENT_ALREADY_DECIDED"
    over = _pay(api, inv, "60000.01", "BANK-OVER")
    assert over.json()["error"]["code"] == "OVERPAYMENT"  # 40,000 still RECORDED from NO-KEY + 60,000.01


def test_missing_idempotency_key_rejected(api: Api) -> None:
    _, inv = _billed_tenant(api, "Key Co")
    h = api.platform.headers(False, None)
    r = api.client.post(
        "/api/v1/platform/payments",
        headers=h,
        json={
            "invoice_id": inv["id"],
            "amount": "1",
            "currency": "TZS",
            "method": "CASH",
            "reference": "C-1",
            "received_on": "2026-11-03",
        },
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_credit_adjustment_and_currency_mismatch(api: Api) -> None:
    _, inv = _billed_tenant(api, "Credit Co")
    r = api.platform.post(
        "/api/v1/platform/credit-adjustments",
        {"invoice_id": inv["id"], "amount": "100000", "reason": "Service outage goodwill"},
    )
    assert r.status_code == 201 and r.json()["status"] == "PAID" and r.json()["balance"] == "0.0000"
    usd = api.platform.post(
        "/api/v1/platform/payments",
        {
            "invoice_id": inv["id"],
            "amount": "1",
            "currency": "USD",
            "method": "CASH",
            "reference": "U-1",
            "received_on": "2026-11-03",
        },
    )
    assert usd.json()["error"]["code"] == "CURRENCY_MISMATCH"


def _evaluate(api: Api, sid: str) -> dict[str, Any]:
    r = api.platform.post(f"/api/v1/platform/subscriptions/{sid}/entitlement/evaluate")
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def test_grace_past_due_suspension_and_reactivation(api: Api) -> None:
    t, inv = _billed_tenant(api, "Late Payer")  # due 2026-11-15; grace 7; suspend after 30
    sid, owner = t["subscription_id"], t["owner"]
    api.clock.set(date(2026, 11, 20))
    assert _evaluate(api, sid)["subscription_status"] == "ACTIVE"  # 5 days overdue, within grace
    api.clock.set(date(2026, 11, 25))
    e = _evaluate(api, sid)
    assert (e["subscription_status"], e["access_state"]) == ("PAST_DUE", "FULL")
    api.clock.set(date(2026, 12, 20))
    e = _evaluate(api, sid)
    assert (e["subscription_status"], e["access_state"], e["changed"]) == ("SUSPENDED", "READ_ONLY", True)

    # Read-only: data remains visible, writes are rejected (not silently discarded).
    assert owner.get("/api/v1/tenant/machines").json()["total"] == 1
    w = owner.post("/api/v1/tenant/machines", {"asset_code": "NEW-1", "name": "New"})
    assert w.status_code == 403 and w.json()["error"]["code"] == "SUBSCRIPTION_READ_ONLY"
    assert owner.get("/api/v1/me").json()["tenants"][0]["access_state"] == "READ_ONLY"

    # December invoice also generated while suspended; pay everything -> automatic reactivation.
    dec = api.generate(sid, date(2026, 12, 20))["created"][0]
    for i, invoice in enumerate((inv, dec)):
        p = _pay(api, invoice, invoice["total"], f"BANK-{i}")
        d = api.platform.post(
            f"/api/v1/platform/payments/{p.json()['id']}/decision", {"verified": True, "note": "Bank statement"}
        )
        assert d.status_code == 200
    sub = api.platform.get(f"/api/v1/platform/tenants/{t['tenant']['id']}/subscription").json()
    assert sub["status"] == "ACTIVE"
    assert owner.post("/api/v1/tenant/machines", {"asset_code": "NEW-1", "name": "New"}).status_code == 201


def test_manual_suspension_requires_manual_reactivation_and_cancellation(api: Api) -> None:
    t, _ = _billed_tenant(api, "Manual Co")
    sid = t["subscription_id"]
    today = api.clock.now.date().isoformat()
    s = api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "SUSPENDED", "effective_date": today, "reason": "Contract dispute"},
    )
    assert s.json()["access_state"] == "READ_ONLY"
    assert _evaluate(api, sid)["subscription_status"] == "SUSPENDED"  # no overdue, still suspended
    bad = api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "PAST_DUE", "effective_date": today, "reason": "manual past due"},
    )
    assert bad.status_code == 422
    r = api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "ACTIVE", "effective_date": today, "reason": "Dispute resolved"},
    )
    assert r.json()["access_state"] == "FULL"
    c = api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "CANCELLED", "effective_date": "2026-12-01", "reason": "Customer exit"},
    )
    assert c.json()["subscription_status"] == "ACTIVE"  # scheduled, still billable until 2026-12-01
    api.clock.set(date(2026, 12, 1))
    c2 = _evaluate(api, sid)
    assert c2["subscription_status"] == "CANCELLED" and c2["access_state"] == "READ_ONLY"
    tenant = api.platform.get(f"/api/v1/platform/tenants/{t['tenant']['id']}").json()
    assert tenant["status"] == "CLOSED"
    gen = api.platform.post(f"/api/v1/platform/subscriptions/{sid}/invoices/generate", {"as_of": "2026-11-01"})
    assert gen.json()["error"]["code"] == "NOT_BILLABLE"
    dash = api.platform.get("/api/v1/platform/dashboard").json()
    assert dash["churn_events_30d"] == 1


def test_activation_requires_verified_company(api: Api) -> None:
    t = api.onboard("Unverified Co", price="1")
    r = api.platform.post(
        f"/api/v1/platform/subscriptions/{t['subscription_id']}/transitions",
        {"to_status": "ACTIVE", "effective_date": "2026-11-01", "reason": "try"},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "TENANT_NOT_VERIFIED"
