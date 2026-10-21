"""Field expenses, receipts, fuel events and approval requests (R1-G). Expense evidence (amount, supplier,
attribution, GPS, receipts, the policy version applied) is immutable; only the approval decision changes."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
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


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class ExpenseStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"  # kept as evidence; never counts toward cost or custody


class ExpensePaidFrom(StrEnum):
    CASH_CUSTODY = "CASH_CUSTODY"  # paid from a supervisor's cash in hand (reduces custody once approved)
    COMPANY = "COMPANY"  # paid by the office (bank, card, credit account)


class FuelEventType(StrEnum):
    PURCHASE = "PURCHASE"  # bought from a supplier (into a machine when machine_id is set, else into stock)
    ISSUE = "ISSUE"  # issued from stock into a machine
    USAGE = "USAGE"  # consumption log (quantity only; no cost)


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ExpenseCategory(UuidPk, SyncRevisioned, Deactivatable, Timestamps, Base):
    __tablename__ = "expense_category"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_expense_category_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class Expense(UuidPk, Base):
    __tablename__ = "expense"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_expense_client"),
        CheckConstraint("amount > 0", name="ck_expense_amount"),
        CheckConstraint("paid_from <> 'CASH_CUSTODY' OR custodian_staff_id IS NOT NULL", name="ck_expense_custodian"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_category.id"), nullable=False, index=True)
    supplier: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    incurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine.id"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"), index=True)
    paid_from: Mapped[ExpensePaidFrom] = mapped_column(_enum(ExpensePaidFrom), nullable=False)
    custodian_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"), index=True)
    status: Mapped[ExpenseStatus] = mapped_column(_enum(ExpenseStatus), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    receipt_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gps_status: Mapped[str | None] = mapped_column(String(24))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # API | SYNC
    device_id: Mapped[str | None] = mapped_column(String(128))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class ExpenseAttachment(UuidPk, Base):
    """Receipt/photo evidence linked to an expense (content lives in `capture_attachment`). Immutable."""

    __tablename__ = "expense_attachment"
    __table_args__ = (UniqueConstraint("expense_id", "attachment_id", name="uq_expense_attachment"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense.id"), nullable=False, index=True)
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("capture_attachment.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class FuelEvent(UuidPk, Base):
    """Immutable fuel log. `attributed_cost` = litres x unit_price (0 for USAGE)."""

    __tablename__ = "fuel_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_fuel_event_client"),
        CheckConstraint("litres > 0", name="ck_fuel_litres"),
        CheckConstraint("event_type = 'PURCHASE' OR machine_id IS NOT NULL", name="ck_fuel_machine"),
        CheckConstraint("event_type = 'USAGE' OR unit_price IS NOT NULL", name="ck_fuel_price"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[FuelEventType] = mapped_column(_enum(FuelEventType), nullable=False)
    litres: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(MONEY)
    attributed_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine.id"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"), index=True)
    expense_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("expense.id"))
    meter_reading: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    supplier: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ApprovalRequest(UuidPk, Base):
    """Human approval of a subject above its policy limit; the decider must not be the requester."""

    __tablename__ = "approval_request"
    __table_args__ = (UniqueConstraint("tenant_id", "subject_type", "subject_id", name="uq_approval_subject"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)  # EXPENSE
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # why approval is needed (policy evaluation)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(_enum(ApprovalStatus), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
