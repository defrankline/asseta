"""Notification persistence. A notification belongs to one recipient in one context: a tenant (`tenant_id`) or the
platform console (`tenant_id` NULL). RLS confines reads to the recipient (app.actor_id) in that context."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.notification.types import Severity


def _enum(cls: type[StrEnum]) -> Enum:
    return Enum(cls, native_enum=False, length=24)


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"  # queued or waiting for retry / quiet hours / rate limit
    SENT = "SENT"
    FAILED = "FAILED"  # gave up (attempts exhausted or permanent provider error); debit refunded
    REFUSED_NO_CREDIT = "REFUSED_NO_CREDIT"  # tenant SMS wallet empty: nothing sent, nothing debited
    INVALID_NUMBER = "INVALID_NUMBER"


class Notification(UuidPk, Base):
    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint("recipient_user_id", "dedupe_key", name="uq_notification_dedupe"),
        Index("ix_notification_inbox", "recipient_user_id", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"), index=True)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(48), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[Severity] = mapped_column(_enum(Severity), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))  # web route of the screen to act on
    entity_type: Mapped[str | None] = mapped_column(String(48))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # False: user opted out (SMS only)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(UuidPk, Base):
    """Channel opt-in/out per type. `user_id` NULL = the tenant-wide default (set by the tenant owner); a user's own
    row overrides it. `scope_key` is the tenant id or 'platform'. Mandatory channels ignore preferences."""

    __tablename__ = "notification_preference"
    __table_args__ = (
        Index(
            "uq_notification_pref_user",
            "scope_key",
            "user_id",
            "notification_type",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_notification_pref_default",
            "scope_key",
            "notification_type",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
        ),
    )

    scope_key: Mapped[str] = mapped_column(String(40), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    notification_type: Mapped[str] = mapped_column(String(48), nullable=False)
    in_app: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sms: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class NotificationProfile(Base):
    """A user's own contact details for notifications (normalized MSISDN)."""

    __tablename__ = "notification_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    msisdn: Mapped[str | None] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SmsDelivery(UuidPk, Base):
    """One SMS to one number. `id` is the provider `reference`, so a retried send is identifiable end to end."""

    __tablename__ = "sms_delivery"
    __table_args__ = (
        UniqueConstraint("notification_id", name="uq_sms_delivery_notification"),
        Index("ix_sms_delivery_due", "next_attempt_at", postgresql_where=text("status = 'PENDING'")),
    )

    notification_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notification.id"))
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"), index=True)
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    notification_type: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[Severity] = mapped_column(_enum(Severity), nullable=False)
    msisdn: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    segments: Mapped[int] = mapped_column(Integer, nullable=False)
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False)  # debits the tenant SMS wallet
    status: Mapped[DeliveryStatus] = mapped_column(_enum(DeliveryStatus), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500))
    provider: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
