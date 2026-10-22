"""Gate 7 PUSH/EMAIL channels: device registration lifecycle (register, refresh, deactivate — never delete),
category x severity routing (user > tenant default > built-in, mandatory channels locked), queueing into the
delivery log, dispatch with retries/backoff, provider "unregistered" deactivating the device, console providers,
and isolation (RLS) of devices and deliveries."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import Response
from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.email import ConsoleEmailClient, EmailSendError
from asseta.core.push import PushSendError, PushSettings, build_push_router
from asseta.modules.notification.channel_dispatch import ChannelDispatcher
from asseta.modules.notification.processing import process_event
from asseta.modules.notification.rules import DomainEvent
from tests.support.api import Actor, Api
from tests.support.channels import RecordingEmail, recording_router
from tests.support.notify import member, sql

DEVICES = "/api/v1/me/push-devices"
ROUTING = "/api/v1/tenant/notification-routing"
ANDROID_TOKEN = "fcm-token-" + "a" * 40
IOS_TOKEN = "b" * 64


def _ok(r: Response, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def anomaly(api: Api, tid: str, severity: str, title: str = "Fuel use far above normal") -> None:
    payload = {
        "kind": "FUEL",
        "severity": severity,
        "title": title,
        "body": "EXC-001 used 40% more fuel per hour than usual.",
        "link": "/tenant/cases",
        "audience_permission": "tenant.fleet.alert_manage",
    }
    event = DomainEvent(uuid.uuid4(), "AnomalyDetected", uuid.UUID(tid), payload)
    process_event(event, get_sessionmaker(), api.clock)


def deliveries(tid: str | None = None) -> list[Any]:
    return sql(
        "SELECT id, channel, status, attempts, destination, push_device_id, last_error, severity, title"
        " FROM notification_delivery WHERE tenant_id IS NOT DISTINCT FROM CAST(:t AS uuid) ORDER BY created_at, channel",
        t=tid,
    )


@pytest.fixture
def tenant(api: Api) -> dict[str, Any]:
    t = api.onboard("Push Co", price="1")
    api.activate(t)
    t["mgr"] = member(api, t["tenant"]["id"], "manager", "push-mgr")
    # The owner (also in the anomaly audience) opts out of CRITICAL anomaly e-mail so only the manager's channels
    # are in play below.
    off = [{"category": "ANOMALY", "severity": "CRITICAL", "push": True, "email": False}]
    r = api.client.put(ROUTING, json={"changes": off}, headers=t["owner"].headers(False, None))
    assert r.status_code == 200, r.text
    return t


def register(
    actor: Actor, token: str, platform: str = "ANDROID", tenant: str | None = None, key: str | None = None
) -> Response:
    body = {"platform": platform, "app": "OWNER", "token": token, "app_version": "1.4.0", "device_label": "Pixel 8"}
    h = actor.headers(True, None)
    if tenant is None:
        h.pop("X-Tenant-ID", None)
    else:
        h["X-Tenant-ID"] = tenant
    if key:
        h["Idempotency-Key"] = key
    r: Response = actor.api.client.post(DEVICES, json=body, headers=h)
    return r


def test_device_registration_lifecycle(api: Api, tenant: dict[str, Any]) -> None:
    owner, tid = tenant["owner"], tenant["tenant"]["id"]
    key = str(uuid.uuid4())
    first = _ok(register(owner, ANDROID_TOKEN, tenant=tid, key=key), 201)
    assert first["tenant_id"] == tid and first["active"] and first["token_hint"] == "...aaaaaa"
    assert "token" not in first
    assert _ok(register(owner, ANDROID_TOKEN, tenant=tid, key=key), 201) == first  # idempotent replay
    unbound = _ok(register(owner, IOS_TOKEN, platform="IOS"), 201)  # no tenant context: every context
    assert unbound["tenant_id"] is None
    h = owner.headers(False, None)
    h.pop("X-Tenant-ID")
    listed = _ok(api.client.get(DEVICES, headers=h))
    assert {d["id"] for d in listed["items"]} == {first["id"], unbound["id"]} and listed["total"] == 2

    gone = _ok(api.client.delete(f"{DEVICES}/{first['id']}", headers=h))
    assert gone["active"] is False and gone["deactivation_reason"] == "USER"
    assert _ok(api.client.get(DEVICES, headers=h))["total"] == 1
    assert _ok(api.client.get(DEVICES, headers=h, params={"include_inactive": True}))["total"] == 2
    back = _ok(register(owner, ANDROID_TOKEN, tenant=tid), 201)  # same token again: reactivated, not duplicated
    assert back["id"] == first["id"] and back["active"] and back["deactivation_reason"] is None
    rows = sql(
        "SELECT count(*) FROM push_device WHERE user_id = (SELECT id FROM app_user WHERE email = :e)", e=owner.email
    )
    assert rows[0][0] == 2
    actions = [
        r.action for r in sql("SELECT action FROM audit_event WHERE entity_type = 'push_device' ORDER BY occurred_at")
    ]
    assert (
        actions.count("notification.push_device.registered") == 3 and "notification.push_device.deactivated" in actions
    )

    # Another user cannot see or deactivate it (API and RLS), and an unknown tenant context is refused.
    mgr = tenant["mgr"]
    mh = mgr.headers(False, None)
    mh.pop("X-Tenant-ID")
    assert _ok(api.client.get(DEVICES, headers=mh))["total"] == 0
    assert api.client.delete(f"{DEVICES}/{first['id']}", headers=mh).status_code == 404
    other = api.onboard("Other Co", price="1")
    assert register(owner, "x" * 40, tenant=other["tenant"]["id"]).status_code == 403
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.USER, None, uuid.uuid4())
        assert s.execute(text("SELECT count(*) FROM push_device")).scalar_one() == 0
    assert api.client.post(DEVICES, json={"platform": "IOS", "app": "OWNER", "token": IOS_TOKEN}).status_code == 401


def test_routing_preferences_and_mandatory_channels(api: Api, tenant: dict[str, Any]) -> None:
    owner, mgr = tenant["owner"], tenant["mgr"]
    cells = {(c["category"], c["severity"]): c for c in _ok(mgr.get(ROUTING))}
    assert len(cells) == 15
    assert (cells[("ANOMALY", "INFO")]["push"], cells[("ANOMALY", "INFO")]["email"]) == (False, False)
    assert (cells[("ANOMALY", "WARNING")]["push"], cells[("ANOMALY", "WARNING")]["email"]) == (True, False)
    assert cells[("ANOMALY", "CRITICAL")]["email"] is True and cells[("ACTION", "INFO")]["push"] is True
    assert cells[("ANOMALY", "INFO")]["source"] == "BUILT_IN" and cells[("ANOMALY", "INFO")]["in_app"] is True
    assert cells[("REMINDER", "WARNING")]["mandatory_channels"] == ["EMAIL"]  # access-restriction notice

    def put(actor: Actor, changes: list[dict[str, Any]], default: bool = False) -> Response:
        r: Response = api.client.put(
            ROUTING, json={"changes": changes, "tenant_default": default}, headers=actor.headers(False, None)
        )
        return r

    refused = put(mgr, [{"category": "REMINDER", "severity": "WARNING", "push": True, "email": False}])
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "MANDATORY_CHANNEL"
    assert put(mgr, [{"category": "ANOMALY", "severity": "INFO", "push": True, "email": True}], True).status_code == 403
    tenant_default = put(owner, [{"category": "ANOMALY", "severity": "INFO", "push": True, "email": False}], True)
    cell = next(c for c in _ok(tenant_default) if (c["category"], c["severity"]) == ("ANOMALY", "INFO"))
    assert cell["source"] == "TENANT_DEFAULT" and cell["push"] is True
    mine = {(c["category"], c["severity"]): c for c in _ok(mgr.get(ROUTING))}
    assert mine[("ANOMALY", "INFO")]["push"] is True and mine[("ANOMALY", "INFO")]["source"] == "TENANT_DEFAULT"
    _ok(put(mgr, [{"category": "ANOMALY", "severity": "INFO", "push": False, "email": True}]))
    mine = {(c["category"], c["severity"]): c for c in _ok(mgr.get(ROUTING))}
    assert (mine[("ANOMALY", "INFO")]["push"], mine[("ANOMALY", "INFO")]["email"]) == (False, True)
    assert mine[("ANOMALY", "INFO")]["source"] == "USER"
    platform = _ok(api.platform.get("/api/v1/platform/notification-routing"))
    assert len(platform) == 15 and all(c["source"] == "BUILT_IN" for c in platform)


def test_severity_routes_to_channels_and_dispatch(api: Api, tenant: dict[str, Any]) -> None:
    tid, mgr = tenant["tenant"]["id"], tenant["mgr"]
    android = _ok(register(mgr, ANDROID_TOKEN, tenant=tid), 201)
    ios = _ok(register(mgr, IOS_TOKEN, platform="IOS"), 201)
    elsewhere = api.onboard("Elsewhere Co", price="1")
    api.activate(elsewhere)
    member(api, elsewhere["tenant"]["id"], "manager", "push-mgr")  # same person, also a member there
    mgr2 = Actor(api, mgr.subject, sorted(api.idp.memberships[mgr.subject]), elsewhere["tenant"]["id"], mgr.email)
    _ok(register(mgr2, "c" * 40, tenant=elsewhere["tenant"]["id"]), 201)  # bound to the other tenant only

    anomaly(api, tid, "INFO", "Info only")  # built-in: in-app only
    assert deliveries(tid) == []
    anomaly(api, tid, "WARNING", "Warning")  # built-in: push to both devices of this context, no e-mail
    warning = deliveries(tid)
    assert sorted((d.channel, str(d.push_device_id)) for d in warning) == sorted(
        [("PUSH", android["id"]), ("PUSH", ios["id"])]
    )
    anomaly(api, tid, "CRITICAL", "Critical")  # built-in: push + e-mail
    critical = [d for d in deliveries(tid) if d.title == "Critical"]
    assert sorted(d.channel for d in critical) == ["EMAIL", "PUSH", "PUSH"]
    assert next(d for d in critical if d.channel == "EMAIL").destination == mgr.email

    router, fcm, apns = recording_router()
    email = RecordingEmail()
    dispatcher = ChannelDispatcher(get_sessionmaker(), router, email, api.clock)
    summary = dispatcher.dispatch_due()
    assert summary.sent == 5 and summary.failed == 0
    assert len(fcm.sent) == 2 and len(apns.sent) == 2 and len(email.sent) == 1
    message, reference = fcm.sent[0]
    assert message.token == ANDROID_TOKEN and message.high_priority and message.data["tenant_id"] == tid
    assert reference in {str(d.id) for d in deliveries(tid)}
    assert email.sent[0][0].subject == "Asseta: Critical" and "/tenant/cases" in email.sent[0][0].text
    assert {d.status for d in deliveries(tid)} == {"SENT"}

    log = _ok(tenant["owner"].get("/api/v1/tenant/notification-deliveries", channel="PUSH"))
    assert log["total"] == 4 and {i["status"] for i in log["items"]} == {"SENT"}
    assert "destination" not in log["items"][0]
    assert mgr.get("/api/v1/tenant/notification-deliveries").status_code == 403  # needs tenant.notification.manage
    assert _ok(elsewhere["owner"].get("/api/v1/tenant/notification-deliveries"))["total"] == 0


def test_retries_backoff_and_unregistered_token_deactivates_device(api: Api, tenant: dict[str, Any]) -> None:
    tid, mgr = tenant["tenant"]["id"], tenant["mgr"]
    android = _ok(register(mgr, ANDROID_TOKEN, tenant=tid), 201)
    _ok(register(mgr, IOS_TOKEN, platform="IOS", tenant=tid), 201)
    anomaly(api, tid, "CRITICAL")
    router, fcm, apns = recording_router()
    email = RecordingEmail()
    fcm.failures.append(PushSendError("FCM rejected the message: NOT_FOUND", unregistered=True, status_code=404))
    apns.failures += [PushSendError("APNs rejected the message: 503", retryable=True, status_code=503)] * 2
    email.failures.append(EmailSendError("Mail server replied 550", retryable=False, smtp_code=550))
    dispatcher = ChannelDispatcher(get_sessionmaker(), router, email, api.clock)

    first = dispatcher.dispatch_due()
    assert (first.sent, first.retried, first.failed, first.undeliverable, first.devices_deactivated) == (0, 1, 1, 1, 1)
    rows = {d.channel + ":" + str(d.push_device_id): d for d in deliveries(tid)}
    assert rows[f"PUSH:{android['id']}"].status == "UNDELIVERABLE"
    assert rows["EMAIL:None"].status == "FAILED" and "550" in rows["EMAIL:None"].last_error
    device = sql("SELECT deactivated_at, deactivation_reason FROM push_device WHERE id = :i", i=android["id"])[0]
    assert device.deactivated_at is not None and device.deactivation_reason == "PROVIDER_UNREGISTERED"

    ios_row = next(d for d in deliveries(tid) if d.channel == "PUSH" and d.status == "PENDING")
    assert ios_row.attempts == 1
    assert dispatcher.dispatch_due().sent == 0  # backoff: not due yet
    api.clock.set_at(api.clock.now + timedelta(seconds=61))
    assert dispatcher.dispatch_due().retried == 1  # second failure, backoff doubles
    api.clock.set_at(api.clock.now + timedelta(seconds=60))
    assert dispatcher.dispatch_due().sent == 0
    api.clock.set_at(api.clock.now + timedelta(seconds=61))
    assert dispatcher.dispatch_due().sent == 1 and len(apns.sent) == 1
    assert sql("SELECT attempts, status FROM notification_delivery WHERE id = :i", i=ios_row.id)[0] == (3, "SENT")

    # The deactivated device is no longer targeted; delivery rows are immutable once final.
    anomaly(api, tid, "WARNING", "After deactivation")
    later = [d for d in deliveries(tid) if d.title == "After deactivation"]
    assert [d.channel for d in later] == ["PUSH"] and str(later[0].push_device_id) != android["id"]
    with pytest.raises(Exception, match="not permitted"):
        sql("UPDATE notification_delivery SET status = 'PENDING' WHERE id = :i", i=ios_row.id)


def test_console_providers_mark_sent_without_sending(api: Api, tenant: dict[str, Any]) -> None:
    tid, mgr = tenant["tenant"]["id"], tenant["mgr"]
    _ok(register(mgr, ANDROID_TOKEN, tenant=tid), 201)
    anomaly(api, tid, "CRITICAL")
    dispatcher = ChannelDispatcher(
        get_sessionmaker(), build_push_router(PushSettings()), ConsoleEmailClient(), api.clock
    )
    assert dispatcher.dispatch_due().sent == 2
    providers = {r[0] for r in sql("SELECT provider FROM notification_delivery WHERE tenant_id = :t", t=tid)}
    assert providers == {"console-android", "console"}
