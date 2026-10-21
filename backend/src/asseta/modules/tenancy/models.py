"""Tenant registry (platform-owned) and tenant settings."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk


class TenantStatus(StrEnum):
    ONBOARDING = "ONBOARDING"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class TenantAccessState(StrEnum):
    """Derived by the entitlement service from subscription state + versioned entitlement policy."""

    FULL = "FULL"
    READ_ONLY = "READ_ONLY"
    BLOCKED = "BLOCKED"


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Tenant(UuidPk, Timestamps, Base):
    __tablename__ = "tenant"

    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(64), unique=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", native_enum=False, length=16), nullable=False
    )
    verification_note: Mapped[str | None] = mapped_column(Text)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", native_enum=False, length=16), nullable=False
    )
    access_state: Mapped[TenantAccessState] = mapped_column(
        Enum(TenantAccessState, name="tenant_access_state", native_enum=False, length=16), nullable=False
    )
    access_state_reason: Mapped[str | None] = mapped_column(String(200))
    access_state_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    keycloak_group_id: Mapped[str | None] = mapped_column(String(64))
    # Bumped only by company-detail edits (access-state changes by the entitlement service do not race them).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TenantSettings(Timestamps, Base):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
