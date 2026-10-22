"""DEC-022 (b): rules -> recipients (permission / assignment / mandate aware, tenant-isolated), preferences
(mandatory channels cannot be disabled), inbox API, reminders idempotent per period."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.notification.processing import process_event
from asseta.modules.notification.reminders import run_reminders
from asseta.modules.notification.rules import DomainEvent
from tests.support.api import Actor, Api
from tests.support.finance import setup_finance
from tests.support.notify import drain, member, platform_owner, replay, sql, sync_mirror

NOV1 = date(2026, 11, 1)
INBOX = "/api/v1/tenant/notifications"


def emit(api: Api, tenant_id: str | None, event_type: str, payload: dict[str, Any]) -> int:
    event = DomainEvent(uuid.uuid4(), event_type, uuid.UUID(tenant_id) if tenant_id else None, payload)
    return process_event(event, get_sessionmaker(), api.clock)


def payment_event(n: int = 1) -> dict[str, Any]:
    return {
        "payment_id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "amount": f"{n}000",
        "currency": "TZS",
        "method": "CASH",
    }


def types(actor: Actor, path: str = INBOX) -> list[str]:
    r = actor.get(path)
    assert r.status_code == 200, r.text
    return [n["type"] for n in r.json()["items"]]


def test_rules_resolve_recipients_by_permission_and_never_cross_tenants(api: Api) -> None:
    a = api.onboard("Notify A", price="1")
    b = api.onboard("Notify B", price="1")
    tid = a["tenant"]["id"]
    accountant = member(api, tid, "accountant", "acct-a")
    manager = member(api, tid, "manager", "mgr-a")
    other_acct = member(api, b["tenant"]["id"], "accountant", "acct-b")
    assert emit(api, tid, "CustomerPaymentRecorded", payment_event()) == 2  # owner + accountant hold finance.verify
    assert types(accountant) == ["CUSTOMER_PAYMENT_TO_VERIFY"]
    assert types(a["owner"]) == ["CUSTOMER_PAYMENT_TO_VERIFY"]
    assert types(manager) == [] and types(other_acct) == []
    item = accountant.get(INBOX).json()["items"][0]
    assert item["target"] == {
        "entity": "customer_payment",
        "id": item["target"]["id"],
        "path": "/tenant/customer-payments",
    }
    assert item["priority"] == "NORMAL" and item["tenant_id"] == tid
    # Another user cannot read it, even by id; another tenant context does not see it.
    assert manager.get(f"{INBOX}/{item['id']}").status_code == 404
    assert other_acct.get(f"{INBOX}/{item['id']}").status_code == 404

    # Supervisor concerned (machine assignment -> linked login) gets tracking alerts with the alert managers.
    sup = member(api, tid, "supervisor", "sup-a")
    machine = a["owner"].post("/api/v1/tenant/machines", {"asset_code": "EX-9", "name": "CAT 320"}).json()
    staff = (
        a["owner"]
        .post("/api/v1/tenant/staff", {"full_name": "Asha", "kind": "SUPERVISOR", "keycloak_subject": sup.subject})
        .json()
    )
    a["owner"].post(
        f"/api/v1/tenant/machines/{machine['id']}/assignments",
        {"staff_member_id": staff["id"], "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    alert = {
        "alert_id": str(uuid.uuid4()),
        "type": "TAMPER",
        "severity": "CRITICAL",
        "machine_id": machine["id"],
        "event_time": api.clock.now.isoformat(),
    }
    emit(api, tid, "TrackingAlertRaised", alert)
    n = sup.get(INBOX).json()["items"][0]
    assert (n["type"], n["severity"], n["priority"]) == ("TRACKING_ALERT", "CRITICAL", "HIGH")
    assert "EX-9" in n["title"]
    assert "TRACKING_ALERT" in types(manager)  # manager holds tenant.fleet.alert_manage
    assert "TRACKING_ALERT" not in types(accountant)


def test_platform_events_reach_platform_staff_only(api: Api) -> None:
    owner = platform_owner(api)
    t = api.onboard("Platform Notify", price="100")
    api.activate(t)
    api.add_machines(t["owner"], 1, enroll_on=NOV1)
    inv = api.generate(t["subscription_id"], NOV1)["created"][0]
    api.platform.post(
        "/api/v1/platform/payments",
        {
            "invoice_id": inv["id"],
            "amount": "50",
            "currency": "TZS",
            "method": "CASH",
            "reference": "C-77",
            "received_on": "2026-11-01",
        },
    )
    drain(api)
    platform_types = sorted(types(owner, "/api/v1/platform/notifications"))
    assert platform_types == ["PLATFORM_PAYMENT_AWAITING_VERIFICATION", "SUBSCRIPTION_STATUS_CHANGED"]
    # The tenant hears about its invoice and activation, never the platform's verification queue.
    assert sorted(types(t["owner"])) == ["PLATFORM_INVOICE_ISSUED", "SUBSCRIPTION_STATUS_CHANGED"]
    replay(api, "PlatformPaymentRecorded")  # Kafka redelivery is idempotent
    assert sorted(types(owner, "/api/v1/platform/notifications")) == platform_types


def test_mandate_staff_notified_only_while_mandate_in_force(api: Api) -> None:
    platform_owner(api)
    t = api.onboard("Mandate Notify", price="1")
    tid = t["tenant"]["id"]
    api.idp.users["staff-neema"] = "neema@asseta.local"
    api.idp.memberships.setdefault("staff-neema", set()).add("/platform/platform-owner")
    sync_mirror(api)
    m = api.platform.post(
        "/api/v1/platform/mandates",
        {"tenant_id": tid, "scope": "FULL", "starts_on": NOV1.isoformat(), "consent_reference": "MSA-1"},
    ).json()
    staff_id = next(
        s["user_id"]
        for s in api.platform.get("/api/v1/platform/mandates/staff").json()
        if s["email"] == "neema@asseta.local"
    )
    r = api.platform.post(
        f"/api/v1/platform/mandates/{m['id']}/assignments", {"user_id": staff_id, "role_key": "accountant"}
    )
    assert r.status_code == 200, r.text
    neema = Actor(api, "staff-neema", sorted(api.idp.memberships["staff-neema"]), tid, email="neema@asseta.local")
    emit(api, tid, "CustomerPaymentRecorded", payment_event(1))
    assert types(neema) == ["CUSTOMER_PAYMENT_TO_VERIFY"]
    # A stale Keycloak group alone (mandate ended) never reaches the staff member.
    api.platform.post(f"/api/v1/platform/mandates/{m['id']}/end", {"version": 1, "reason": "Contract ended"})
    api.idp.memberships["staff-neema"].add(f"/tenants/{tid}/accountant")  # pretend Keycloak removal lagged
    sync_mirror(api)
    emit(api, tid, "CustomerPaymentRecorded", payment_event(2))
    rows = sql(
        "SELECT count(*) FROM notification n JOIN app_user u ON u.id = n.recipient_user_id"
        " WHERE u.keycloak_subject = 'staff-neema' AND n.tenant_id = :t",
        t=tid,
    )
    assert rows[0][0] == 1


def test_preferences_honoured_and_mandatory_channels_locked(api: Api) -> None:
    t = api.onboard("Prefs Co", price="1")
    tid = t["tenant"]["id"]
    acct = member(api, tid, "accountant", "acct-p")
    prefs = {p["type"]: p for p in acct.get(f"{INBOX}/preferences").json()}
    assert prefs["SOD_VIOLATION_ATTEMPT"]["mandatory"] and prefs["SOD_VIOLATION_ATTEMPT"]["mandatory_channels"] == [
        "IN_APP"
    ]
    assert "SYSTEM_TEST" not in prefs  # platform-only type
    off = api.client.put(
        f"{INBOX}/preferences",
        headers=acct.headers(False, None),
        json={"changes": [{"type": "CUSTOMER_PAYMENT_TO_VERIFY", "in_app": False, "sms": False}]},
    )
    assert off.status_code == 200, off.text
    locked = api.client.put(
        f"{INBOX}/preferences",
        headers=acct.headers(False, None),
        json={"changes": [{"type": "SOD_VIOLATION_ATTEMPT", "in_app": False, "sms": False}]},
    )
    assert locked.json()["error"]["code"] == "MANDATORY_CHANNEL"
    not_owner = api.client.put(
        f"{INBOX}/preferences",
        headers=acct.headers(False, None),
        json={"tenant_default": True, "changes": [{"type": "APPROVAL_REQUESTED", "in_app": True, "sms": True}]},
    )
    assert not_owner.status_code == 403
    emit(api, tid, "CustomerPaymentRecorded", payment_event())
    emit(
        api,
        tid,
        "SegregationOfDutiesViolation",
        {"action": "verify", "entity_type": "customer_payment", "entity_id": str(uuid.uuid4())},
    )
    assert types(acct) == []  # opted out; SoD goes to access managers (owner), mandatory in-app there
    assert sorted(types(t["owner"])) == ["CUSTOMER_PAYMENT_TO_VERIFY", "SOD_VIOLATION_ATTEMPT"]
    # Tenant-wide default by the owner applies to users without their own row.
    default = api.client.put(
        f"{INBOX}/preferences",
        headers=t["owner"].headers(False, None),
        json={
            "tenant_default": True,
            "changes": [{"type": "CUSTOMER_PAYMENT_TO_VERIFY", "in_app": False, "sms": False}],
        },
    )
    assert default.status_code == 200, default.text
    mgr2 = member(api, tid, "accountant", "acct-q")
    emit(api, tid, "CustomerPaymentRecorded", payment_event(3))
    assert types(mgr2) == []


def test_inbox_read_flows_and_counts(api: Api) -> None:
    t = api.onboard("Inbox Co", price="1")
    tid = t["tenant"]["id"]
    for i in range(3):
        emit(api, tid, "CustomerPaymentRecorded", payment_event(i + 1))
    o = t["owner"]
    assert o.get(f"{INBOX}/unread-count").json() == {"count": 3}
    first = o.get(INBOX).json()["items"][0]["id"]
    r = o.post(f"{INBOX}/read", {"ids": [first]})
    assert r.json() == {"updated": 1, "unread": 2}
    assert o.get(INBOX, unread_only=True).json()["total"] == 2
    assert o.post(f"{INBOX}/read-all").json() == {"updated": 2, "unread": 0}
    assert o.get(INBOX, q="3000").json()["total"] == 1
    assert sql_error("UPDATE notification SET title = 'x' WHERE id = :i", i=first)


def sql_error(query: str, **params: Any) -> bool:
    try:
        sql(query, **params)
    except Exception as exc:
        return "not permitted" in str(exc)
    return False


def test_reminders_idempotent_per_period(api: Api) -> None:
    platform_owner(api)
    t = api.onboard("Reminder Co", price="1000", terms_days=14)
    api.activate(t)
    api.add_machines(t["owner"], 1, enroll_on=NOV1)
    api.generate(t["subscription_id"], NOV1)  # due 2026-11-15
    api.clock.set(date(2026, 11, 20))
    first = run_reminders(get_sessionmaker(), api.clock.now)
    again = run_reminders(get_sessionmaker(), api.clock.now)
    assert first.notifications > 0 and again.notifications == 0
    tenant_types = types(t["owner"])
    assert tenant_types.count("PLATFORM_INVOICE_OVERDUE") == 1
    assert "SUBSCRIPTION_RESTRICTION_UPCOMING" in tenant_types  # 5 days overdue, grace 7: warned 3 days ahead
    assert types(api.platform, "/api/v1/platform/notifications").count("PLATFORM_INVOICE_OVERDUE") == 1
    api.clock.set(date(2026, 11, 20) + timedelta(days=1))
    run_reminders(get_sessionmaker(), api.clock.now)
    assert types(t["owner"]).count("PLATFORM_INVOICE_OVERDUE") == 2  # next period, still overdue


def test_real_flows_handover_to_verify_sod_attempt_and_cash_reminder(api: Api) -> None:
    f = setup_finance(api, "Flow Co", "FLOW-1")
    sync_mirror(api)  # the finance helper's role actors exist only as tokens; mirror what Keycloak knows
    r = f.accountant.post(
        "/api/v1/tenant/cash/floats",
        {"staff_member_id": f.sup_staff_id, "amount": "100000", "occurred_at": "2026-11-01T08:00:00+00:00"},
    )
    assert r.status_code == 201, r.text
    h = f.accountant.post(
        "/api/v1/tenant/cash/handovers",
        {"staff_member_id": f.sup_staff_id, "amount": "40000", "handed_at": "2026-11-01T08:30:00+00:00"},
    )
    assert h.status_code == 201, h.text
    sod = f.accountant.post(f"/api/v1/tenant/cash/handovers/{h.json()['id']}/decision", {"verified": True, "note": "x"})
    assert sod.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    # The refused attempt rolled the request back, yet the signal was committed on its own.
    assert sql("SELECT count(*) FROM outbox_event WHERE event_type = 'SegregationOfDutiesViolation'")[0][0] == 1
    drain(api)
    owner_types = types(f.owner)
    assert "CASH_HANDOVER_TO_VERIFY" in owner_types and "SOD_VIOLATION_ATTEMPT" in owner_types
    # End of the tenant-local day: the claimed handover is not verified, so 100,000 is still held -> reminder,
    # once per day (to the supervisor's linked login when mirrored, and to finance verifiers).
    api.clock.set_at(datetime(2026, 11, 1, 17, 0, tzinfo=UTC))  # 20:00 Dar es Salaam (cutoff 19:00)
    run_reminders(get_sessionmaker(), api.clock.now)
    run_reminders(get_sessionmaker(), api.clock.now)
    rows = sql(
        "SELECT recipient_user_id, title, body FROM notification"
        " WHERE notification_type = 'CASH_NOT_HANDED_OVER' AND tenant_id = :t",
        t=f.tid,
    )
    assert len(rows) >= 1 and all("100000" in r.body for r in rows)
    assert len({r.recipient_user_id for r in rows}) == len(rows)  # re-run did not duplicate
