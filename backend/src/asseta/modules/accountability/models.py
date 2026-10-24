"""Integrity and oversight records (accountability design D): refused attempts kept as security events, and the
office's controlled outcome for conflicted/rejected offline operations. Both append-only."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk


def _enum(cls: type[StrEnum], length: int = 32) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class SecurityEventKind(StrEnum):
    PERMISSION_DENIED = "PERMISSION_DENIED"  # a request refused for a missing permission
    SEGREGATION_OF_DUTIES = "SEGREGATION_OF_DUTIES"  # an attempt to approve/verify/acknowledge one's own record


class SecurityEvent(UuidPk, Base):
    """A refused attempt. Written in its own transaction (the refused request rolls back). Facts only: who, what was
    asked, which permission or rule refused it."""

    __tablename__ = "security_event"
    __table_args__ = (Index("ix_security_event_tenant_time", "tenant_id", "occurred_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[SecurityEventKind] = mapped_column(_enum(SecurityEventKind), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    # The login subject: names the actor even when a first-ever request was refused (its user row rolled back).
    actor_subject: Mapped[str | None] = mapped_column(String(64))
    permission: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str | None] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    request_method: Mapped[str | None] = mapped_column(String(8))
    request_path: Mapped[str | None] = mapped_column(String(300))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class SyncResolutionOutcome(StrEnum):
    DISMISSED = "DISMISSED"  # reviewed; nothing to re-apply (reason recorded)
    RECAPTURED = "RECAPTURED"  # the information was captured again as another record


class SyncOperationResolution(UuidPk, Base):
    """The office's outcome for one conflicted/rejected client operation (one per operation, append-only)."""

    __tablename__ = "sync_operation_resolution"
    __table_args__ = (UniqueConstraint("operation_id", name="uq_sync_operation_resolution_op"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client_operation.id"), nullable=False)
    outcome: Mapped[SyncResolutionOutcome] = mapped_column(_enum(SyncResolutionOutcome), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recaptured_entity_type: Mapped[str | None] = mapped_column(String(40))
    recaptured_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
