"""Offline sync persistence (§6): device sessions, idempotent client operations, policy snapshots handed to
devices, and resumable blob upload sessions."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, LargeBinary, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class DeviceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"  # lost/stolen/offboarded: next contact -> wipe instruction


class OperationStatus(StrEnum):
    ACKED = "ACKED"
    REJECTED = "REJECTED"
    CONFLICT = "CONFLICT"
    QUARANTINED = "QUARANTINED"  # tenant read-only/suspended: kept, not applied, replayable after reactivation


class DeviceSession(UuidPk, Base):
    __tablename__ = "device_session"
    __table_args__ = (
        Index(
            "uq_device_session_active",
            "tenant_id",
            "device_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)  # ANDROID | IOS
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[DeviceStatus] = mapped_column(_enum(DeviceStatus), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offline_grant_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_clock_offset_s: Mapped[float | None] = mapped_column()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)


class ClientOperation(Base):
    """Server record of every device operation id: the idempotency + audit anchor for offline sync."""

    __tablename__ = "client_operation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)  # device-generated op id
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    device_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device_session.id"), nullable=False)
    op_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[OperationStatus] = mapped_column(_enum(OperationStatus), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at_device: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DevicePolicySnapshot(UuidPk, Base):
    """Policy versions handed to a device for offline enforcement (audit of what the field was told)."""

    __tablename__ = "device_policy_snapshot"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    device_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device_session.id"), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False)  # "machine:<id>" / "tenant"
    version_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    version_stamp: Mapped[str] = mapped_column(String(80), nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BlobUploadSession(UuidPk, Base):
    __tablename__ = "blob_upload_session"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    device_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device_session.id"), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # OPEN | COMPLETE
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("capture_attachment.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BlobChunk(Base):
    __tablename__ = "blob_chunk"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blob_upload_session.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


# Tables delivered to devices by delta pull; each carries a server-monotonic `sync_revision` maintained by trigger.
SYNCED_TABLES = ("job", "machine", "job_site", "customer", "rental_contract", "staff_member", "machine_assignment")
