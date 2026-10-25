"""PUSH and EMAIL channels: queueing (inside the notification transaction) and dispatch (worker, one transaction per
delivery, `FOR UPDATE SKIP LOCKED`). Retries use exponential backoff on retryable provider errors; a provider saying a
push token is gone deactivates that device (`PROVIDER_UNREGISTERED`) so it is never used again. Delivery is
at-least-once (a crash between send and commit re-sends with the same delivery id as provider reference)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import ColumnElement, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from asseta.core.db import DbScope, apply_scope
from asseta.core.email import EmailClient, EmailSendError, OutboundEmail
from asseta.core.push import PushMessage, PushRouter, PushSendError
from asseta.modules.identity.models import AppUser
from asseta.modules.notification.channel_models import (
    ChannelDeliveryStatus,
    DeviceDeactivation,
    NotificationDelivery,
    PushDevice,
)
from asseta.modules.notification.models import Notification
from asseta.modules.notification.settings import NotificationSettings, get_notification_settings
from asseta.modules.notification.types import Channel, Severity

log = structlog.get_logger()


def _delivery(
    n: Notification, channel: Channel, destination: str, now: datetime, device: uuid.UUID | None
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "notification_id": n.id,
        "tenant_id": n.tenant_id,
        "recipient_user_id": n.recipient_user_id,
        "channel": channel.value,
        "push_device_id": device,
        "destination": destination,
        "notification_type": n.notification_type,
        "severity": n.severity,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "status": ChannelDeliveryStatus.PENDING,
        "attempts": 0,
        "next_attempt_at": now,
        "created_at": now,
        "updated_at": now,
    }


def push_data(d: NotificationDelivery, n: Notification | None) -> dict[str, str]:
    """Push payload (string values only): the notification, plus the exact record it is about — `entity` /
    `entity_id` and, for accountability records, `kind` / `record_id` — so a tap opens that record."""
    data = {
        "notification_id": str(d.notification_id),
        "type": d.notification_type,
        "severity": d.severity.value,
        "tenant_id": str(d.tenant_id) if d.tenant_id else "",
        "link": d.link or "",
    }
    if n is not None:
        if n.entity_type:
            data["entity"] = n.entity_type
        if n.entity_id:
            data["entity_id"] = str(n.entity_id)
        for key in ("kind", "record_id"):
            if isinstance((value := (n.data or {}).get(key)), str):
                data[key] = value
    return data


def target_devices(session: Session, user_id: uuid.UUID, tenant_id: uuid.UUID | None) -> list[PushDevice]:
    """The user's active devices for this context: bound to the notification's tenant or unbound (platform
    notifications only reach unbound devices). A token re-registered later by another user (handed-over phone)
    belongs to that user only."""
    newer = aliased(PushDevice)
    context: ColumnElement[bool] = PushDevice.tenant_id.is_(None)
    if tenant_id is not None:
        context = context | (PushDevice.tenant_id == tenant_id)
    taken = exists().where(
        newer.token_sha256 == PushDevice.token_sha256,
        newer.user_id != PushDevice.user_id,
        newer.deactivated_at.is_(None),
        newer.last_registered_at > PushDevice.last_registered_at,
    )
    return list(
        session.execute(
            select(PushDevice).where(
                PushDevice.user_id == user_id, PushDevice.deactivated_at.is_(None), context, ~taken
            )
        ).scalars()
    )


def queue_push(session: Session, n: Notification, now: datetime) -> int:
    rows = [
        _delivery(n, Channel.PUSH, str(d.id), now, d.id)
        for d in target_devices(session, n.recipient_user_id, n.tenant_id)
    ]
    for row in rows:
        session.execute(insert(NotificationDelivery).values(**row).on_conflict_do_nothing())
    return len(rows)


def queue_email(session: Session, n: Notification, now: datetime) -> int:
    address = session.execute(
        select(AppUser.email).where(AppUser.id == n.recipient_user_id, AppUser.is_active.is_(True))
    ).scalar_one_or_none()
    if not address or "@" not in address:
        return 0
    row = _delivery(n, Channel.EMAIL, address, now, None)
    session.execute(insert(NotificationDelivery).values(**row).on_conflict_do_nothing())
    return 1


@dataclass
class ChannelDispatchSummary:
    sent: int = 0
    retried: int = 0
    failed: int = 0
    undeliverable: int = 0
    devices_deactivated: int = 0


class ChannelDispatcher:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        push: PushRouter,
        email: EmailClient,
        clock: Callable[[], datetime],
        settings: NotificationSettings | None = None,
    ):
        self._factory, self._push, self._email, self._clock = session_factory, push, email, clock
        self._settings = settings or get_notification_settings()

    def dispatch_due(self, limit: int = 100) -> ChannelDispatchSummary:
        summary = ChannelDispatchSummary()
        now = self._clock()
        with self._factory() as s, s.begin():
            apply_scope(s, DbScope.SYSTEM, None, None)
            ids = list(
                s.execute(
                    select(NotificationDelivery.id)
                    .where(
                        NotificationDelivery.status == ChannelDeliveryStatus.PENDING,
                        NotificationDelivery.next_attempt_at <= now,
                    )
                    .order_by(NotificationDelivery.next_attempt_at)
                    .limit(limit)
                ).scalars()
            )
        for delivery_id in ids:
            self.dispatch_one(delivery_id, summary)
        return summary

    def dispatch_one(
        self, delivery_id: uuid.UUID, summary: ChannelDispatchSummary | None = None
    ) -> ChannelDeliveryStatus | None:
        summary = summary or ChannelDispatchSummary()
        now = self._clock()
        with self._factory() as s, s.begin():
            apply_scope(s, DbScope.SYSTEM, None, None)
            d = s.execute(
                select(NotificationDelivery)
                .where(
                    NotificationDelivery.id == delivery_id, NotificationDelivery.status == ChannelDeliveryStatus.PENDING
                )
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
            if d is None:
                return None
            if d.channel == Channel.PUSH.value:
                self._send_push(s, d, now, summary)
            else:
                self._send_email(d, now, summary)
            d.updated_at = now
            return d.status

    def _send_push(self, s: Session, d: NotificationDelivery, now: datetime, summary: ChannelDispatchSummary) -> None:
        device = s.get(PushDevice, d.push_device_id) if d.push_device_id else None
        if device is None or device.deactivated_at is not None:
            d.status, d.last_error = ChannelDeliveryStatus.UNDELIVERABLE, "Device is no longer registered"
            summary.undeliverable += 1
            return
        message = PushMessage(
            token=device.token,
            title=d.title,
            body=d.body,
            data=push_data(d, s.get(Notification, d.notification_id)),
            high_priority=d.severity is not Severity.INFO,
            collapse_key=d.notification_type,
            app=device.app.value,
        )
        d.attempts += 1
        try:
            result = self._push.for_platform(device.platform.value).send(message, reference=str(d.id))
        except PushSendError as exc:
            if exc.unregistered:
                device.deactivated_at, device.deactivation_reason = now, DeviceDeactivation.PROVIDER_UNREGISTERED
                device.updated_at = now
                d.status, d.last_error = ChannelDeliveryStatus.UNDELIVERABLE, str(exc)[:500]
                summary.undeliverable += 1
                summary.devices_deactivated += 1
                log.info("push_device_unregistered", device_id=str(device.id), delivery_id=str(d.id))
                return
            self._failed(d, now, str(exc), exc.retryable, summary)
            return
        except Exception as exc:  # transport surprises are treated as transient
            self._failed(d, now, f"Push provider error: {type(exc).__name__}", True, summary)
            return
        d.status, d.sent_at, d.provider, d.last_error = ChannelDeliveryStatus.SENT, now, result.provider, None
        d.provider_message_id = result.message_id[:200] if result.message_id else None
        summary.sent += 1

    def _send_email(self, d: NotificationDelivery, now: datetime, summary: ChannelDispatchSummary) -> None:
        base = (self._settings.web_base_url or "").rstrip("/")
        lines = [d.body]
        if d.link:
            lines += ["", f"Open in Asseta: {base}{d.link}" if base else f"Open in Asseta: {d.link}"]
        lines += ["", "You receive this e-mail because of your Asseta notification settings."]
        d.attempts += 1
        try:
            result = self._email.send(
                OutboundEmail(to=d.destination, subject=f"Asseta: {d.title}"[:200], text="\n".join(lines)),
                reference=str(d.id),
            )
        except EmailSendError as exc:
            self._failed(d, now, str(exc), exc.retryable, summary)
            return
        except Exception as exc:
            self._failed(d, now, f"E-mail provider error: {type(exc).__name__}", True, summary)
            return
        d.status, d.sent_at, d.provider, d.last_error = ChannelDeliveryStatus.SENT, now, result.provider, None
        d.provider_message_id = result.message_id[:200] if result.message_id else None
        summary.sent += 1

    def _failed(
        self, d: NotificationDelivery, now: datetime, error: str, retryable: bool, summary: ChannelDispatchSummary
    ) -> None:
        d.last_error = error[:500]
        if retryable and d.attempts < self._settings.channel_max_attempts:
            delay = self._settings.channel_retry_base_seconds * 2 ** (d.attempts - 1)
            d.next_attempt_at = now + timedelta(seconds=delay)
            summary.retried += 1
            return
        d.status = ChannelDeliveryStatus.FAILED
        summary.failed += 1
        log.warning("channel_delivery_failed", delivery_id=str(d.id), channel=d.channel, attempts=d.attempts)
