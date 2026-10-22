"""Append-only audit trail for sensitive changes (actor, tenant, source, policy version, before/after)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from asseta.core.correlation import get_correlation_id
from asseta.core.db import Base, UuidPk, utcnow


class AuditEvent(UuidPk, Base):
    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_event_tenant_time", "tenant_id", "occurred_at"),)  # audit log views

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_roles: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(64))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Managed-service mandate the actor was working under (DEC-018); stamped from the request session.
    mandate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)


class AuditActor:
    """Who is acting; built from the authenticated principal or a worker identity."""

    def __init__(self, user_id: uuid.UUID | None, roles: list[str], source: str, device_id: str | None = None):
        self.user_id = user_id
        self.roles = roles
        self.source = source
        self.device_id = device_id


class AuditService:
    def __init__(self, session: Session):
        self._session = session

    def record(
        self,
        *,
        actor: AuditActor,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | str,
        tenant_id: uuid.UUID | None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
        policy_version: str | None = None,
    ) -> None:
        self._session.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor.user_id,
                actor_roles=actor.roles,
                device_id=actor.device_id,
                source=actor.source,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                policy_version=policy_version,
                before=before,
                after=after,
                reason=reason,
                correlation_id=get_correlation_id(),
                mandate_id=self._session.info.get("mandate_id"),
            )
        )
