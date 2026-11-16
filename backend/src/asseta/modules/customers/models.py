"""Customers and the tenant rate card. Customers buy machine hours (orders); the rate card prices them per machine
category. Prices are owner-approved Decimal terms, versioned by effective date."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, SyncRevisioned, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable

MONEY = Numeric(18, 4)
HOURS = Numeric(12, 2)


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class CustomerKind(StrEnum):
    REGISTERED = "REGISTERED"
    WALK_IN = "WALK_IN"  # display name (+ optional phone) only; code WALK-<nnnnn>; may be upgraded later


class Customer(UuidPk, SyncRevisioned, Deactivatable, Timestamps, Base):
    """`code` is unique per tenant; when a person leaves it blank the server assigns CUST-<nnnnn>."""

    __tablename__ = "customer"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_customer_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(64))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    kind: Mapped[CustomerKind] = mapped_column(
        _enum(CustomerKind, 16), nullable=False, default=CustomerKind.REGISTERED, server_default="REGISTERED"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class RentalRatePolicy(UuidPk, Base):
    """Tenant rate card, versioned by effective date (default hourly rate per machine category)."""

    __tablename__ = "rental_rate_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "machine_category_id", "effective_from", name="uq_rate_card"),
        CheckConstraint("hourly_rate >= 0", name="ck_rate_card_rate"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    machine_category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine_category.id"), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
