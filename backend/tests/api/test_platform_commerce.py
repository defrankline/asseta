"""DEC-022 (a): product catalog lifecycle, ad-hoc invoices with mixed lines, per-line payment allocation,
exactly-once fulfilment (SMS wallet credit, subscription period settlement + entitlement, service), void reversal."""

import uuid
from datetime import date, timedelta
from typing import Any

from asseta.core.audit import AuditActor
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.platform_billing.allocation import AllocationService
from asseta.modules.platform_billing.enums import SmsWalletEntryType
from asseta.modules.platform_billing.fulfilment import FulfilmentService
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.sms_wallet import SmsWalletService
from tests.support.api import Api
from tests.support.notify import drain, replay, sql

NOV1 = date(2026, 11, 1)
ACTOR = AuditActor(None, ["test"], "test")


def products(api: Api) -> dict[str, str]:
    p = api.platform
    sms = p.post(
        "/api/v1/platform/products",
        {
            "code": "SMS-1000",
            "name": "SMS bundle 1,000",
            "product_type": "SMS_BUNDLE",
            "sms_credits": 1000,
            "prices": {"TZS": "25000"},
        },
    )
    assert sms.status_code == 201, sms.text
    svc = p.post(
        "/api/v1/platform/products",
        {"code": "INSTALL", "name": "Tracker installation", "product_type": "SERVICE", "prices": {"TZS": "150000"}},
    )
    sub = p.post(
        "/api/v1/platform/products", {"code": "SUB", "name": "Subscription", "product_type": "SUBSCRIPTION_FEE"}
    )
    assert svc.status_code == 201 and sub.status_code == 201, (svc.text, sub.text)
    return {"sms": sms.json()["id"], "svc": svc.json()["id"], "sub": sub.json()["id"]}


def tenant(api: Api, name: str) -> dict[str, Any]:
    t = api.onboard(name, price="100000", tax="18", terms_days=14)
    api.activate(t)
    api.add_machines(t["owner"], 2, enroll_on=NOV1)
    return t


def raise_invoice(api: Api, tid: str, lines: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    r = api.platform.post("/api/v1/platform/invoices", {"tenant_id": tid, "lines": lines, **extra})
    assert r.status_code == 201, r.text
    return dict(r.json())


def pay(api: Api, amount: str, ref: str, verify: bool = True, **target: Any) -> dict[str, Any]:
    body = {
        "amount": amount,
        "currency": "TZS",
        "method": "BANK_TRANSFER",
        "reference": ref,
        "received_on": NOV1.isoformat(),
        **target,
    }
    r = api.platform.post("/api/v1/platform/payments", body)
    assert r.status_code == 201, r.text
    if not verify:
        return dict(r.json())
    v = api.platform_checker.post(
        f"/api/v1/platform/payments/{r.json()['id']}/decision", {"verified": True, "note": "Bank ok"}
    )
    assert v.status_code == 200, v.text
    return dict(v.json())


def wallet(owner: Any) -> dict[str, Any]:
    r = owner.get("/api/v1/tenant/billing/sms-wallet")
    assert r.status_code == 200, r.text
    return dict(r.json())


def test_catalog_lifecycle_and_validation(api: Api) -> None:
    ids = products(api)
    p = api.platform
    bad = p.post("/api/v1/platform/products", {"code": "SMS-X", "name": "No credits", "product_type": "SMS_BUNDLE"})
    assert bad.json()["error"]["code"] == "SMS_CREDITS_REQUIRED"
    priced_sub = p.post(
        "/api/v1/platform/products",
        {"code": "SUB2", "name": "Sub", "product_type": "SUBSCRIPTION_FEE", "prices": {"TZS": "1"}},
    )
    assert priced_sub.json()["error"]["code"] == "SUBSCRIPTION_PRICE_FROM_RATE"
    dup = p.post("/api/v1/platform/products", {"code": "INSTALL", "name": "Again", "product_type": "SERVICE"})
    assert dup.json()["error"]["code"] == "DUPLICATE_PRODUCT_CODE"
    assert [x["code"] for x in p.get("/api/v1/platform/products", q="sms").json()["items"]] == ["SMS-1000"]
    detail = p.get(f"/api/v1/platform/products/{ids['sms']}").json()
    assert detail["prices"] == {"TZS": "25000.0000"} and detail["version"] == 1
    edit = {"name": "SMS bundle 1k", "sms_credits": 1000, "prices": {"TZS": "24000", "USD": "10"}, "version": 1}
    edited = p.put(f"/api/v1/platform/products/{ids['sms']}", edit)
    assert edited.status_code == 200 and edited.json()["version"] == 2, edited.text
    assert p.put(f"/api/v1/platform/products/{ids['sms']}", edit).json()["error"]["code"] == "STALE_VERSION"
    off = p.post(f"/api/v1/platform/products/{ids['svc']}/deactivate", {"reason": "Discontinued"})
    assert off.json()["is_active"] is False
    assert [x["code"] for x in p.get("/api/v1/platform/products").json()["items"]] == ["SMS-1000", "SUB"]
    assert len(p.get("/api/v1/platform/products", include_inactive=True).json()["items"]) == 3
    t = tenant(api, "Catalog Co")
    refused = api.platform.post(
        "/api/v1/platform/invoices", {"tenant_id": t["tenant"]["id"], "lines": [{"product_id": ids["svc"]}]}
    )
    assert refused.json()["error"]["code"] == "PRODUCT_INACTIVE"
    assert p.post(f"/api/v1/platform/products/{ids['svc']}/reactivate", {"reason": "Back"}).json()["is_active"]
    # Tenants have no access to the platform catalog.
    assert t["owner"].get("/api/v1/platform/products").status_code == 403


def test_adhoc_mixed_invoice_allocation_fulfilment_exactly_once_and_void(api: Api) -> None:
    ids = products(api)
    t = tenant(api, "Mixed Co")
    tid, owner = t["tenant"]["id"], t["owner"]
    lines = [
        {"product_id": ids["sub"], "period_start": NOV1.isoformat()},
        {"product_id": ids["sms"], "quantity": "2", "unit_price": "20000"},
        {"product_id": ids["svc"], "discount_percent": "10"},
    ]
    preview = api.platform.post("/api/v1/platform/invoices/preview", {"tenant_id": tid, "lines": lines})
    assert preview.status_code == 200 and preview.json()["id"] is None, preview.text
    inv = raise_invoice(api, tid, lines, notes="Onboarding pack")
    assert inv["kind"] == "AD_HOC" and inv["invoice_number"].startswith("AST-2026-")
    assert [(x["line_type"], x["amount"]) for x in inv["lines"]] == [
        ("SUBSCRIPTION_FEE", "236000.0000"),  # 2 machines x 100,000 + 18% VAT from the negotiated rate
        ("SMS_BUNDLE", "40000.0000"),
        ("SERVICE", "135000.0000"),
        ("TAX", "31500.0000"),  # 18% of the taxable catalog lines only
    ]
    assert inv["total"] == preview.json()["total"] == "442500.0000"
    assert inv["lines"][1]["sms_credits"] == 2000
    again = api.platform.post(
        "/api/v1/platform/invoices",
        {"tenant_id": tid, "lines": [{"product_id": ids["sub"], "period_start": "2026-11-01"}]},
    )
    assert again.json()["error"]["code"] == "PERIOD_ALREADY_BILLED"
    # The scheduler sees the period as billed: no double billing.
    gen = api.generate(t["subscription_id"], NOV1)
    assert gen["created"] == [] and gen["existing_periods"] == ["2026-11-01"]

    sms_line = inv["lines"][1]["id"]
    p1 = pay(api, "40000", "BANK-SMS", invoice_id=inv["id"], allocations=[{"line_id": sms_line, "amount": "40000"}])
    assert [(a["line_id"], a["amount"]) for a in p1["allocations"]] == [(sms_line, "40000.0000")]
    view = api.platform.get(f"/api/v1/platform/invoices/{inv['id']}").json()
    assert [x["fulfilment_status"] for x in view["lines"]] == [None, "FULFILLED", None, None]
    assert (view["status"], view["balance"]) == ("PARTIALLY_PAID", "402500.0000")
    assert wallet(owner)["balance"] == 2000

    # Tenant-level payment, default order: oldest open invoice, line order -> settles the subscription line.
    p2 = pay(api, "236000", "BANK-SUB", tenant_id=tid)
    assert p2["invoice_id"] is None and p2["unallocated"] == "0.0000"
    view = api.platform.get(f"/api/v1/platform/invoices/{inv['id']}").json()
    assert [x["fulfilment_status"] for x in view["lines"]] == ["FULFILLED", "FULFILLED", None, None]
    assert [x["paid"] for x in view["lines"]] == ["236000.0000", "40000.0000", "0.0000", "0.0000"]

    # Exactly once: redelivered events, re-run fulfilment and a duplicate verification change nothing.
    drain(api)
    replay(api, "PlatformPaymentVerified")
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.PLATFORM, None, None)
        invoice = BillingRepository(s).invoice(inv["id"])
        states = AllocationService(s, ACTOR, NOV1).line_states(invoice.id)
        assert FulfilmentService(s, ACTOR, NOV1).fulfil_settled(invoice, states) == []
    dup = api.platform_checker.post(
        f"/api/v1/platform/payments/{p1['id']}/decision", {"verified": True, "note": "again"}
    )
    assert dup.json()["error"]["code"] == "PAYMENT_ALREADY_DECIDED"
    assert wallet(owner)["balance"] == 2000
    assert sql("SELECT count(*) FROM sms_wallet_entry WHERE tenant_id = :t", t=tid)[0][0] == 1
    assert sql("SELECT count(*) FROM platform_line_fulfilment WHERE invoice_id = :i", i=inv["id"])[0][0] == 2
    tenant_view = owner.get("/api/v1/tenant/billing/invoices").json()
    assert tenant_view[0]["lines"][1]["fulfilment_status"] == "FULFILLED"

    # Void: allocations released (money becomes credit), unused SMS credits debited back, settlement reversed.
    voided = api.platform.post(f"/api/v1/platform/invoices/{inv['id']}/void", {"reason": "Issued to wrong branch"})
    assert voided.status_code == 200, voided.text
    v = voided.json()
    assert (v["status"], v["balance"], v["void_reason"]) == ("VOIDED", "0.0000", "Issued to wrong branch")
    assert [x["fulfilment_status"] for x in v["lines"]] == ["REVERSED", "REVERSED", None, None]
    assert wallet(owner)["balance"] == 0
    assert api.platform.post(f"/api/v1/platform/invoices/{inv['id']}/void", {"reason": "again"}).status_code == 409
    payments = api.platform.get("/api/v1/platform/payments", tenant_id=tid).json()["items"]
    assert {x["reference"]: x["unallocated"] for x in payments} == {"BANK-SMS": "40000.0000", "BANK-SUB": "236000.0000"}

    # Re-bill the period and apply the released credit to it.
    rebill = raise_invoice(api, tid, [{"product_id": ids["sub"], "period_start": NOV1.isoformat()}])
    applied = api.platform_checker.post(f"/api/v1/platform/payments/{p2['id']}/allocations", {})
    assert applied.status_code == 200 and applied.json()["unallocated"] == "0.0000", applied.text
    re_view = api.platform.get(f"/api/v1/platform/invoices/{rebill['id']}").json()
    assert (re_view["status"], re_view["lines"][0]["fulfilment_status"]) == ("PAID", "FULFILLED")
    # The voided snapshot is final at the database too.
    r = sql_fail("UPDATE platform_invoice SET status = 'ISSUED' WHERE id = :i", i=inv["id"])
    assert "voided invoice is final" in r


def sql_fail(query: str, **params: Any) -> str:
    try:
        sql(query, **params)
    except Exception as exc:
        return str(exc)
    return ""


def test_void_flags_reversal_when_sms_credits_were_used(api: Api) -> None:
    ids = products(api)
    t = tenant(api, "Used Credits Co")
    tid = t["tenant"]["id"]
    inv = raise_invoice(api, tid, [{"product_id": ids["sms"]}])  # 25,000 + 18% VAT
    pay(api, inv["total"], "MPESA-1", invoice_id=inv["id"])
    assert wallet(t["owner"])["balance"] == 1000
    with get_sessionmaker().begin() as s:  # 990 credits spent on SMS
        apply_scope(s, DbScope.SYSTEM, None, None)
        SmsWalletService(s).post(t["tenant"]["id"], SmsWalletEntryType.SMS_DEBIT, -990, "test", uuid.uuid4())
    v = api.platform.post(f"/api/v1/platform/invoices/{inv['id']}/void", {"reason": "Customer dispute"}).json()
    assert v["lines"][0]["fulfilment_status"] == "REVERSAL_FLAGGED"
    assert wallet(t["owner"])["balance"] == 0
    effect = sql("SELECT effect, reversal_note FROM platform_line_fulfilment WHERE invoice_id = :i", i=inv["id"])[0]
    assert effect[0]["reversed_credits"] == 10 and "990 credits already used" in effect[1]
    drain(api)  # FULFILMENT_REVERSAL_FLAGGED reaches platform staff with void permission (no recipients mirrored here)


def test_unpaid_bundle_never_restricts_access_but_unpaid_subscription_line_does(api: Api) -> None:
    ids = products(api)
    t = tenant(api, "Entitlement Co")
    tid, sid = t["tenant"]["id"], t["subscription_id"]
    raise_invoice(api, tid, [{"product_id": ids["sms"]}])
    sub_inv = raise_invoice(api, tid, [{"product_id": ids["sub"], "period_start": NOV1.isoformat()}])
    api.clock.set(NOV1 + timedelta(days=14 + 7 + 2))  # past due date + grace
    r = api.platform.post(f"/api/v1/platform/subscriptions/{sid}/entitlement/evaluate")
    assert r.json()["subscription_status"] == "PAST_DUE", r.text
    pay(api, sub_inv["total"], "BANK-LATE", invoice_id=sub_inv["id"])
    r = api.platform.post(f"/api/v1/platform/subscriptions/{sid}/entitlement/evaluate")
    assert r.json()["subscription_status"] == "ACTIVE"  # the SMS bundle is still unpaid and overdue: no effect


def test_explicit_allocation_validation(api: Api) -> None:
    ids = products(api)
    t = tenant(api, "Alloc Co")
    other = tenant(api, "Alloc Other")
    inv = raise_invoice(api, t["tenant"]["id"], [{"product_id": ids["svc"]}])
    foreign = raise_invoice(api, other["tenant"]["id"], [{"product_id": ids["svc"]}])
    line = inv["lines"][0]["id"]
    body = {
        "invoice_id": inv["id"],
        "amount": "1000",
        "currency": "TZS",
        "method": "CASH",
        "reference": "C-1",
        "received_on": NOV1.isoformat(),
    }
    over = api.platform.post(
        "/api/v1/platform/payments", {**body, "allocations": [{"line_id": line, "amount": "2000"}]}
    )
    assert over.status_code == 422
    cross = api.platform.post(
        "/api/v1/platform/payments",
        {**body, "allocations": [{"line_id": foreign["lines"][0]["id"], "amount": "1000"}]},
    )
    assert cross.json()["error"]["code"] == "ALLOCATION_MISMATCH"
    too_much = api.platform.post("/api/v1/platform/payments", {**body, "amount": "999999999"})
    assert too_much.json()["error"]["code"] == "OVERPAYMENT"
    # Tenants see their own invoices only.
    mine = t["owner"].get("/api/v1/tenant/billing/invoices").json()
    assert [i["id"] for i in mine] == [inv["id"]]
