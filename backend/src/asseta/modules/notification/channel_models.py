"""Persistence for the PUSH and EMAIL channels (Gate 7): registered mobile devices, per category x severity routing
preferences and the delivery log the worker dispatches with retries.

Push tokens are stored as issued (the providers need the exact token) together with a SHA-256 for lookups and
de-duplication. Protection: FORCE RLS confines rows to the owning user (or the SYSTEM-scope worker), the API never
returns a token (only a short hint), and the database relies on encryption at rest. Application-level encryption
would need a managed key (KMS) that R1 deployments do not have; this is recorded in the Gate 7 notes."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.notification.types import Severity


def _enum(cls: type[StrEnum]) -> Enum:
    return Enum(cls, native_enum=False, length=24)


class DevicePlatform(StrEnum):
    ANDROID = "ANDROID"
    IOS = "IOS"


class DeviceApp(StrEnum):
    OWNER = "OWNER"
    SUPERVISOR = "SUPERVISOR"


class DeviceDeactivation(StrEnum):
    USER = "USER"  # the user signed out / removed the device
    PROVIDER_UNREGISTERED = "PROVIDER_UNREGISTERED"  # FCM/APNs said the token is gone for good


class ChannelDeliveryStatus(StrEnum):
    PENDING = "PENDING"  # queued or waiting for a retry
    SENT = "SENT"  # accepted by the provider
    FAILED = "FAILED"  # attempts exhausted or permanent provider error
    UNDELIVERABLE = "UNDELIVERABLE"  # device unregistered/deactivated or no address: nothing to send to


class PushDevice(UuidPk, Base):
    __tablename__ = "push_device"
    __table_args__ = (
        UniqueConstraint("user_id", "token_sha256", name="uq_push_device_user_token"),
        Index("ix_push_device_token", "token_sha256"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"))  # NULL: every context of the user
    platform: Mapped[DevicePlatform] = mapped_column(_enum(DevicePlatform), nullable=False)
    app: Mapped[DeviceApp] = mapped_column(_enum(DeviceApp), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(32))
    device_label: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivation_reason: Mapped[DeviceDeactivation | None] = mapped_column(_enum(DeviceDeactivation))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class NotificationRouting(UuidPk, Base):
    """Which optional channels (PUSH, EMAIL) a category x severity goes to. `user_id` NULL = the tenant-wide default
    set by the tenant owner; a user's own row overrides it; without either the built-in default applies."""

    __tablename__ = "notification_routing"
    __table_args__ = (
        Index(
            "uq_notification_routing_user",
            "scope_key",
            "user_id",
            "category",
            "severity",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_notification_routing_default",
            "scope_key",
            "category",
            "severity",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
        ),
    )

    scope_key: Mapped[str] = mapped_column(String(40), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[Severity] = mapped_column(_enum(Severity), nullable=False)
    push: Mapped[bool] = mapped_column(Boolean, nullable=False)
    email: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class NotificationDelivery(UuidPk, Base):
    """One PUSH (to one device) or EMAIL (to one address) of a notification. `id` doubles as the provider
    reference (APNs `apns-id`, e-mail `X-Asseta-Reference`), so a retried send is identifiable end to end."""

    __tablename__ = "notification_delivery"
    __table_args__ = (
        UniqueConstraint("notification_id", "channel", "destination", name="uq_notification_delivery_target"),
        Index("ix_notification_delivery_due", "next_attempt_at", postgresql_where=text("status = 'PENDING'")),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notification.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"), index=True)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(8), nullable=False)  # PUSH | EMAIL
    push_device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("push_device.id"))
    destination: Mapped[str] = mapped_column(String(320), nullable=False)  # e-mail address, or the device id
    notification_type: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[Severity] = mapped_column(_enum(Severity), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[ChannelDeliveryStatus] = mapped_column(_enum(ChannelDeliveryStatus), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500))
    provider: Mapped[str | None] = mapped_column(String(24))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
