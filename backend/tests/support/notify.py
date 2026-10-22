"""DEC-022 helpers: IdP-backed users (so the Keycloak membership mirror knows them), a stand-in for the Kafka hop
(outbox rows fed straight into the notification pipeline), a recording SMS client and direct DB reads."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Engine, create_engine, text

from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.core.sms import SmsSendError, SmsSendResult, normalize_msisdn
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.notification.processing import process_event
from asseta.modules.notification.realtime import RealtimePublisher
from asseta.modules.notification.rules import DomainEvent
from tests.support.api import PLATFORM_SUBJECT, Actor, Api

OWNER_PATH = "/platform/platform-owner"


def owner_engine() -> Engine:
    return create_engine(get_settings().migration_database_url)


def sql(query: str, **params: Any) -> list[Any]:
    engine = owner_engine()
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.scope', 'system', true)"))
        result = conn.execute(text(query), params)
        rows = list(result.all()) if result.returns_rows else []
    engine.dispose()
    return rows


def sync_mirror(api: Api) -> None:
    with get_sessionmaker().begin() as session:
        AuthzSyncService(api.idp).pull_role_mirror(session)


def platform_owner(api: Api) -> Actor:
    """The test platform owner as a Keycloak group member (mirrored -> addressable by notification rules)."""
    api.idp.users[PLATFORM_SUBJECT] = "platform@asseta.local"
    api.idp.memberships.setdefault(PLATFORM_SUBJECT, set()).add(OWNER_PATH)
    api.idp.ensure_group(OWNER_PATH)
    sync_mirror(api)
    return api.platform


def member(api: Api, tenant_id: str, role: str, subject: str, sync: bool = True) -> Actor:
    """A tenant user present in Keycloak (and therefore in the membership mirror)."""
    email = f"{subject}@notify.example.com"
    api.idp.users[subject] = email
    path = f"/tenants/{tenant_id}/{role}"
    api.idp.ensure_group(path)
    api.idp.memberships.setdefault(subject, set()).add(path)
    if sync:
        sync_mirror(api)
    return Actor(api, subject, sorted(api.idp.memberships[subject]), tenant_id, email=email)


def user_id(subject: str) -> uuid.UUID:
    return uuid.UUID(str(sql("SELECT id FROM app_user WHERE keycloak_subject = :s", s=subject)[0][0]))


def drain(api: Api, publisher: RealtimePublisher | None = None) -> int:
    """Kafka stand-in: process every unpublished outbox event once, in order, then mark it published."""
    rows = sql(
        "SELECT id, event_type, tenant_id, payload, correlation_id FROM outbox_event"
        " WHERE published_at IS NULL ORDER BY created_at, id"
    )
    created = 0
    for r in rows:
        event = DomainEvent(r.id, r.event_type, r.tenant_id, r.payload, r.correlation_id)
        created += process_event(event, get_sessionmaker(), api.clock, publisher)
    if rows:
        sql("UPDATE outbox_event SET published_at = now() WHERE id = ANY(:ids)", ids=[r.id for r in rows])
    return created


def replay(api: Api, event_type: str) -> int:
    """Redeliver already-processed events of a type (Kafka at-least-once)."""
    rows = sql(
        "SELECT id, event_type, tenant_id, payload, correlation_id FROM outbox_event WHERE event_type = :t",
        t=event_type,
    )
    return sum(
        process_event(
            DomainEvent(r.id, r.event_type, r.tenant_id, r.payload, r.correlation_id), get_sessionmaker(), api.clock
        )
        for r in rows
    )


class RecordingSms:
    """SmsClient double: records sends; can fail the next N sends."""

    def __init__(self) -> None:
        self.sent: list[tuple[tuple[str, ...], str, str | None]] = []
        self.failures: list[SmsSendError] = []

    def send(self, recipients: Sequence[str], message: str, reference: str | None = None) -> SmsSendResult:
        if self.failures:
            raise self.failures.pop(0)
        to = tuple(normalize_msisdn(r) for r in recipients)
        self.sent.append((to, message, reference))
        return SmsSendResult("fake", to, reference)
