"""Turns intents into per-recipient notifications: resolve audience (mandate-aware), apply preferences (mandatory
channels win), persist idempotently (unique recipient + dedupe key, so redelivered events and re-run reminders
never duplicate), queue SMS deliveries, and collect real-time pushes to publish after the transaction commits.
Runs in SYSTEM scope (cross-recipient fan-out); every row carries the event's tenant."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.modules.notification.dto import notification_dto
from asseta.modules.notification.models import (
    DeliveryStatus,
    Notification,
    NotificationPreference,
    NotificationProfile,
    SmsDelivery,
)
from asseta.modules.notification.realtime import RealtimePublisher, entity_channel, user_channel
from asseta.modules.notification.recipients import Directory, Recipient
from asseta.modules.notification.rules import Audience, Intent
from asseta.modules.notification.segments import sms_segments
from asseta.modules.notification.settings import NotificationSettings, get_notification_settings
from asseta.modules.notification.types import TYPES, Channel, NotificationType


def scope_key(tenant_id: uuid.UUID | None) -> str:
    return str(tenant_id) if tenant_id else "platform"


@dataclass(frozen=True)
class Channels:
    in_app: bool
    sms: bool
    sms_opted_in: bool  # explicit opt-in (needed for low-priority SMS)


def effective_channels(
    session: Session, user_id: uuid.UUID, tenant_id: uuid.UUID | None, ntype: NotificationType
) -> Channels:
    rows = session.execute(
        select(NotificationPreference).where(
            NotificationPreference.scope_key == scope_key(tenant_id),
            NotificationPreference.notification_type == ntype.code,
            or_(NotificationPreference.user_id == user_id, NotificationPreference.user_id.is_(None)),
        )
    ).scalars()
    by_user = {r.user_id is not None: r for r in rows}
    chosen = by_user.get(True) or by_user.get(False)
    in_app = chosen.in_app if chosen else True
    sms = chosen.sms if chosen else (ntype.sms_default and not ntype.low_priority)
    opted = bool(chosen and chosen.sms)
    return Channels(
        in_app or Channel.IN_APP in ntype.mandatory,
        sms or Channel.SMS in ntype.mandatory,
        opted or Channel.SMS in ntype.mandatory,
    )


def unread_count(session: Session, user_id: uuid.UUID, tenant_id: uuid.UUID | None) -> int:
    ctx = Notification.tenant_id == tenant_id if tenant_id else Notification.tenant_id.is_(None)
    return int(
        session.execute(
            select(func.count()).where(
                Notification.recipient_user_id == user_id,
                ctx,
                Notification.in_app.is_(True),
                Notification.read_at.is_(None),
            )
        ).scalar_one()
    )


class NotificationEngine:
    def __init__(self, session: Session, today: date, now: datetime, settings: NotificationSettings | None = None):
        self._s, self._now = session, now
        self._dir = Directory(session, today)
        self._settings = settings or get_notification_settings()
        self.pending: list[tuple[str, dict[str, Any]]] = []
        self.created: list[Notification] = []

    def _resolve(self, tenant_id: uuid.UUID | None, a: Audience) -> tuple[uuid.UUID | None, list[Recipient]]:
        if a.kind == "platform_permission":
            return None, self._dir.platform_permission(a.value)
        if tenant_id is None:
            return None, []  # tenant audiences need the event's tenant: never guessed
        if a.kind == "tenant_permission":
            return tenant_id, self._dir.tenant_permission(tenant_id, a.value)
        if a.kind == "tenant_role":
            return tenant_id, self._dir.tenant_role(tenant_id, a.value)
        if a.kind == "tenant_user":
            return tenant_id, self._dir.tenant_user(tenant_id, uuid.UUID(a.value))
        if a.kind == "tenant_staff":
            return tenant_id, self._dir.tenant_staff(tenant_id, uuid.UUID(a.value))
        raise ValueError(f"unknown audience {a.kind}")

    def deliver(
        self, tenant_id: uuid.UUID | None, intents: list[Intent], source_event_id: uuid.UUID | None = None
    ) -> list[Notification]:
        made: list[Notification] = []
        for intent in intents:
            ntype = TYPES[intent.type]
            seen: set[tuple[uuid.UUID | None, uuid.UUID]] = set()
            for audience in intent.audiences:
                context, recipients = self._resolve(tenant_id, audience)
                for r in recipients:
                    if (context, r.user_id) in seen:
                        continue
                    seen.add((context, r.user_id))
                    n = self._one(context, r, intent, ntype, source_event_id)
                    if n is not None:
                        made.append(n)
        self.created += made
        return made

    def _one(
        self,
        tenant_id: uuid.UUID | None,
        r: Recipient,
        intent: Intent,
        ntype: NotificationType,
        source_event_id: uuid.UUID | None,
    ) -> Notification | None:
        ch = effective_channels(self._s, r.user_id, tenant_id, ntype)
        wants_sms = ch.sms and (not ntype.low_priority or ch.sms_opted_in)
        if not ch.in_app and not wants_sms:
            return None
        nid = self._s.execute(
            insert(Notification)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                recipient_user_id=r.user_id,
                notification_type=ntype.code,
                category=ntype.category.value,
                severity=intent.severity or ntype.severity,
                title=intent.title[:200],
                body=intent.body,
                link=intent.link,
                entity_type=intent.entity_type,
                entity_id=intent.entity_id,
                data=intent.data,
                in_app=ch.in_app,
                dedupe_key=intent.dedupe[:200],
                source_event_id=source_event_id,
                created_at=self._now,
            )
            .on_conflict_do_nothing(constraint="uq_notification_dedupe")
            .returning(Notification.id)
        ).scalar_one_or_none()
        if nid is None:
            return None  # already notified (event redelivery, reminder re-run)
        n = self._s.get(Notification, nid)
        assert n is not None
        if wants_sms:
            self._queue_sms(n, r)
        if ch.in_app:
            self._s.flush()
            self.pending.append(
                (user_channel(r.user_id, tenant_id), {"type": "notification", "payload": notification_dto(n)})
            )
            count = unread_count(self._s, r.user_id, tenant_id)
            self.pending.append(
                (user_channel(r.user_id, tenant_id), {"type": "unread_count", "payload": {"count": count}})
            )
        return n

    def _queue_sms(self, n: Notification, r: Recipient) -> None:
        msisdn = self._s.execute(
            select(NotificationProfile.msisdn).where(NotificationProfile.user_id == r.user_id)
        ).scalar_one_or_none()
        if not msisdn:
            return
        text = f"Asseta: {n.title}. {n.body}"
        if len(text) > self._settings.sms_max_chars:
            text = text[: self._settings.sms_max_chars - 1] + "…"
        self._s.add(
            SmsDelivery(
                id=uuid.uuid4(),
                notification_id=n.id,
                tenant_id=n.tenant_id,
                recipient_user_id=r.user_id,
                notification_type=n.notification_type,
                severity=n.severity,
                msisdn=msisdn,
                text=text,
                segments=sms_segments(text)[0],
                billable=n.tenant_id is not None and not r.via_mandate,
                status=DeliveryStatus.PENDING,
                attempts=0,
                next_attempt_at=self._now,
                created_at=self._now,
                updated_at=self._now,
            )
        )

    def entity_changed(self, tenant_id: uuid.UUID | None, change: dict[str, Any]) -> None:
        self.pending.append((entity_channel(tenant_id), {"type": "entity.changed", "payload": change}))

    def publish(self, publisher: RealtimePublisher) -> int:
        """Call after commit: subscribers must never see rows that could still roll back."""
        for channel, message in self.pending:
            publisher.publish(channel, message)
        sent, self.pending = len(self.pending), []
        return sent
