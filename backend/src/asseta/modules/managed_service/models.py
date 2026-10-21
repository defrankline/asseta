"""Managed-service mandates (DEC-018): a client tenant's written consent lets named platform staff run its account
with the client's own Keycloak roles, only while the mandate is in force."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk


class MandateScope(StrEnum):
    FULL = "FULL"  # any of the client's roles
    OPERATIONS = "OPERATIONS"  # never roles that administer the client's users, roles or mandates


class MandateStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"  # by the client
    ENDED = "ENDED"  # by the platform


class ManagedServiceMandate(UuidPk, Timestamps, Base):
    __tablename__ = "managed_service_mandate"
    __table_args__ = (
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="ck_mandate_dates"),
        Index("uq_mandate_active", "tenant_id", unique=True, postgresql_where=text("status = 'ACTIVE'")),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    scope: Mapped[MandateScope] = mapped_column(String(16), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    consent_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[MandateStatus] = mapped_column(String(16), default=MandateStatus.ACTIVE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(Text)


class MandateAssignment(UuidPk, Timestamps, Base):
    """A named platform staff member holding one of the client's role groups under the mandate."""

    __tablename__ = "mandate_assignment"
    __table_args__ = (
        Index(
            "uq_mandate_assignment_active",
            "mandate_id",
            "user_id",
            "role_key",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index("ix_mandate_assignment_user", "tenant_id", "user_id"),
    )

    mandate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("managed_service_mandate.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    # Keycloak group path, not a FK: the role mirror is rebuilt from Keycloak and must never be blocked by history.
    role_key: Mapped[str] = mapped_column(String(64), nullable=False)
    group_path: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def in_force(mandate: ManagedServiceMandate, today: date) -> bool:
    return (
        mandate.status == MandateStatus.ACTIVE
        and mandate.starts_on <= today
        and (mandate.ends_on is None or mandate.ends_on >= today)
    )


def display_status(mandate: ManagedServiceMandate, today: date) -> str:
    if mandate.status != MandateStatus.ACTIVE:
        return mandate.status.value if isinstance(mandate.status, MandateStatus) else str(mandate.status)
    if mandate.starts_on > today:
        return "SCHEDULED"
    if mandate.ends_on is not None and mandate.ends_on < today:
        return "EXPIRED"
    return "IN_FORCE"
