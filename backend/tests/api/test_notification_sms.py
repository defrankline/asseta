"""DEC-022 SMS channel: phone normalisation, wallet metering per segment, refusal when empty (+ in-app notice),
retry with backoff, permanent failure refund, quiet hours, platform SMS never tenant-billed, and the exact NextSMS
request (Basic auth from settings) through a fake HTTP transport. No real SMS is ever sent."""

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.sms import NextSmsClient, SmsClient, SmsSendError, SmsSettings
from asseta.modules.notification.processing import process_event
from asseta.modules.notification.rules import DomainEvent
from asseta.modules.notification.segments import sms_segments
from asseta.modules.notification.sms_channel import SmsDispatcher
from asseta.modules.platform_billing.enums import SmsWalletEntryType
from asseta.modules.platform_billing.sms_wallet import SmsWalletService
from tests.support.api import Api
from tests.support.notify import RecordingSms, platform_owner, sql

INBOX = "/api/v1/tenant/notifications"
FAKE_URL = "https://sms.test/api/sms/v1/text/single"


def invoice_event(api: Api, tid: str, n: int = 1) -> None:
    payload = {
        "invoice_id": str(uuid.uuid4()),
        "invoice_number": f"AST-2026-{n:07d}",
        "kind": "AD_HOC",
        "total": "1000.0000",
        "currency": "TZS",
        "due_date": "2026-11-15",
    }
    process_event(
        DomainEvent(uuid.uuid4(), "PlatformInvoiceIssued", uuid.UUID(tid), payload), get_sessionmaker(), api.clock
    )


def credit(tid: str, credits: int) -> None:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        SmsWalletService(s).post(uuid.UUID(tid), SmsWalletEntryType.BUNDLE_CREDIT, credits, "test", uuid.uuid4())


def deliveries(tid: str | None = None) -> list[Any]:
    return sql(
        "SELECT id, status, attempts, segments, billable, last_error, next_attempt_at FROM sms_delivery"
        " WHERE tenant_id IS NOT DISTINCT FROM CAST(:t AS uuid) ORDER BY created_at, id",
        t=tid,
    )


def balance(tid: str) -> int:
    return int(sql("SELECT coalesce(sum(credits), 0) FROM sms_wallet_entry WHERE tenant_id = :t", t=tid)[0][0])


def dispatcher(api: Api, client: SmsClient) -> SmsDispatcher:
    return SmsDispatcher(get_sessionmaker(), client, api.clock)


@pytest.fixture
def tenant(api: Api) -> dict[str, Any]:
    t = api.onboard("Sms Co", price="1")
    r = api.client.put(f"{INBOX}/profile", headers=t["owner"].headers(False, None), json={"msisdn": "0712 345 678"})
    assert r.status_code == 200 and r.json()["msisdn"] == "255712345678", r.text
    return t


def test_phone_normalisation_and_rejection(api: Api, tenant: dict[str, Any]) -> None:
    h = tenant["owner"].headers(False, None)
    for raw, expected in (
        ("+255 712 345 678", "255712345678"),
        ("712345678", "255712345678"),
        ("+254 712 345 678", "254712345678"),
    ):
        assert api.client.put(f"{INBOX}/profile", headers=h, json={"msisdn": raw}).json()["msisdn"] == expected
    bad = api.client.put(f"{INBOX}/profile", headers=h, json={"msisdn": "0712 34"})
    assert bad.json()["error"]["code"] == "INVALID_MSISDN"
    assert api.client.put(f"{INBOX}/profile", headers=h, json={"msisdn": None}).json()["msisdn"] is None


def test_wallet_metering_refusal_retry_and_refund(api: Api, tenant: dict[str, Any]) -> None:
    tid, sms = tenant["tenant"]["id"], RecordingSms()
    invoice_event(api, tid, 1)
    [d] = deliveries(tid)
    assert (d.status, d.billable, d.segments) == ("PENDING", True, 1)
    s = dispatcher(api, sms).dispatch_due()
    assert s.refused == 1 and sms.sent == []
    assert deliveries(tid)[0].status == "REFUSED_NO_CREDIT"
    empty = tenant["owner"].get(INBOX).json()["items"]
    assert "SMS_WALLET_EMPTY" in [n["type"] for n in empty]  # the owner is told in-app

    credit(tid, 3)
    invoice_event(api, tid, 2)
    sms.failures.append(SmsSendError("SMS gateway request failed with status 503", 503, True))
    first = dispatcher(api, sms).dispatch_due()
    pending = next(d for d in deliveries(tid) if d.status == "PENDING")
    assert first.retried == 1 and pending.attempts == 1 and pending.next_attempt_at > api.clock.now
    assert balance(tid) == 2  # debited once, before the first attempt
    api.clock.set_at(pending.next_attempt_at)
    assert dispatcher(api, sms).dispatch_due().sent == 1
    assert balance(tid) == 2  # retry does not debit again
    (to, text, reference) = sms.sent[0]
    assert to == ("255712345678",) and reference == str(pending.id) and text.startswith("Asseta: Asseta invoice")
    assert dispatcher(api, sms).dispatch_due().sent == 0  # nothing left: exactly one send per delivery

    invoice_event(api, tid, 3)
    sms.failures.append(SmsSendError("SMS gateway request failed with status 401", 401, False))
    assert dispatcher(api, sms).dispatch_due().failed == 1
    assert balance(tid) == 2  # permanent failure: the debit is refunded
    ledger = sql("SELECT entry_type FROM sms_wallet_entry WHERE tenant_id = :t ORDER BY created_at, id", t=tid)
    assert [r[0] for r in ledger] == ["BUNDLE_CREDIT", "SMS_DEBIT", "SMS_DEBIT", "SMS_REFUND"]
    log = tenant["owner"].get(f"{INBOX}/deliveries").json()
    assert log["total"] == 3 and {x["status"] for x in log["items"]} == {"REFUSED_NO_CREDIT", "SENT", "FAILED"}


def test_quiet_hours_defer_but_critical_goes_through(api: Api, tenant: dict[str, Any]) -> None:
    tid, sms = tenant["tenant"]["id"], RecordingSms()
    credit(tid, 10)
    api.clock.set_at(datetime(2026, 11, 1, 20, 0, tzinfo=UTC))  # 23:00 in Dar es Salaam
    invoice_event(api, tid)
    assert dispatcher(api, sms).dispatch_due().deferred == 1
    [d] = deliveries(tid)
    assert d.next_attempt_at == datetime(2026, 11, 2, 4, 0, tzinfo=UTC)  # 07:00 local
    machine = tenant["owner"].post("/api/v1/tenant/machines", {"asset_code": "Q-1", "name": "Dozer"}).json()
    alert = {
        "alert_id": str(uuid.uuid4()),
        "type": "TAMPER",
        "severity": "CRITICAL",
        "machine_id": machine["id"],
        "event_time": api.clock.now.isoformat(),
    }
    process_event(
        DomainEvent(uuid.uuid4(), "TrackingAlertRaised", uuid.UUID(tid), alert), get_sessionmaker(), api.clock
    )
    assert dispatcher(api, sms).dispatch_due().sent == 1 and "Tamper" in sms.sent[0][1]


def test_platform_staff_sms_is_not_tenant_billed(api: Api) -> None:
    owner = platform_owner(api)
    h = owner.headers(False, None)
    assert api.client.put("/api/v1/platform/notifications/profile", headers=h, json={"msisdn": "0754000111"}).is_success
    opt = api.client.put(
        "/api/v1/platform/notifications/preferences",
        headers=h,
        json={"changes": [{"type": "PLATFORM_PAYMENT_AWAITING_VERIFICATION", "in_app": True, "sms": True}]},
    )
    assert opt.status_code == 200, opt.text
    t = api.onboard("Billing Free", price="1")
    payload = {"payment_id": str(uuid.uuid4()), "invoice_id": None, "amount": "5", "currency": "TZS", "reference": "R"}
    process_event(
        DomainEvent(uuid.uuid4(), "PlatformPaymentRecorded", uuid.UUID(t["tenant"]["id"]), payload),
        get_sessionmaker(),
        api.clock,
    )
    sms = RecordingSms()
    assert dispatcher(api, sms).dispatch_due().sent == 1  # tenant wallet is empty, yet platform SMS goes out
    [d] = deliveries(None)
    assert (d.billable, d.status) == (False, "SENT")
    assert balance(t["tenant"]["id"]) == 0


def test_nextsms_request_shape_auth_from_settings_and_failure_retry(api: Api, tenant: dict[str, Any]) -> None:
    tid = tenant["tenant"]["id"]
    credit(tid, 5)
    seen: list[httpx.Request] = []
    statuses = [500, 200]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(statuses.pop(0), json={"messages": [{"status": "PENDING"}]})

    settings = SmsSettings(
        _env_file=None,
        sms_provider="nextsms",
        nextsms_url=FAKE_URL,
        nextsms_sender_id="ASSETA",
        nextsms_username="demo-user",
        nextsms_password="demo-pass",
    )
    client = NextSmsClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    invoice_event(api, tid)
    [d] = deliveries(tid)
    assert dispatcher(api, client).dispatch_due().retried == 1  # non-2xx = failure, retried with backoff
    api.clock.set_at(deliveries(tid)[0].next_attempt_at)
    assert dispatcher(api, client).dispatch_due().sent == 1
    req = seen[-1]
    assert req.method == "POST" and str(req.url) == FAKE_URL
    assert req.headers["Authorization"] == "Basic " + base64.b64encode(b"demo-user:demo-pass").decode()
    assert req.headers["Content-Type"] == "application/json" and req.headers["Accept"] == "application/json"
    body = json.loads(req.content)
    assert body == {"from": "ASSETA", "to": ["255712345678"], "text": body["text"], "reference": str(d.id)}
    assert body["text"].startswith("Asseta: ") and json.loads(seen[0].content)["reference"] == str(d.id)
    assert balance(tid) == 4


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", (0, "GSM-7")),
        ("a" * 160, (1, "GSM-7")),
        ("a" * 161, (2, "GSM-7")),
        ("€" * 80, (1, "GSM-7")),
        ("€" * 81, (2, "GSM-7")),
        ("Habari 👋", (1, "UCS-2")),
        ("ñ" * 160, (1, "GSM-7")),
        ("ł" * 71, (2, "UCS-2")),
    ],
)
def test_sms_segments(text: str, expected: tuple[int, str]) -> None:
    assert sms_segments(text) == expected


def test_platform_test_send_uses_configured_console_provider(api: Api) -> None:
    r = api.platform.post("/api/v1/platform/notifications/test-send", {"msisdn": "0712345678"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delivery"]["status"] == "SENT" and body["delivery"]["msisdn"] == "255712345678"
    assert body["delivery"]["billable"] is False and body["delivery"]["provider"] == "console"
    inbox = api.platform.get("/api/v1/platform/notifications").json()["items"]
    assert [n["type"] for n in inbox] == ["SYSTEM_TEST"]
    log = api.platform.get("/api/v1/platform/notifications/deliveries").json()
    assert log["total"] == 1
    bad = api.platform.post("/api/v1/platform/notifications/test-send", {"msisdn": "12"})
    assert bad.json()["error"]["code"] == "INVALID_MSISDN"
