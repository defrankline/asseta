"""Versioned policy records: platform default -> tenant default -> machine/site override. Immutable rows."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.policy.schemas import PolicyScope, PolicyType


class PolicyVersion(UuidPk, Base):
    __tablename__ = "policy_version"
    __table_args__ = (
        UniqueConstraint("policy_type", "scope", "tenant_id", "scope_ref_id", "version", name="uq_policy_version"),
        Index("ix_policy_lookup", "policy_type", "tenant_id", "scope", "scope_ref_id", "effective_from"),
    )

    policy_type: Mapped[PolicyType] = mapped_column(Enum(PolicyType, native_enum=False, length=32), nullable=False)
    scope: Mapped[PolicyScope] = mapped_column(Enum(PolicyScope, native_enum=False, length=16), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"))
    scope_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # machine/site id
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
