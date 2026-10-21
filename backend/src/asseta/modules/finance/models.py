"""Tenant hire finance ledger (R1-G): customer hire invoices (immutable once issued), reversals, customer payments
with verification and allocations, supervisor cash custody and handovers. Strictly separate from the platform
subscription ledger (`platform_invoice` & co): no shared tables, numbering, permissions or endpoints."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.jobs.charges import ChargeKind

MONEY = Numeric(18, 4)


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class HireInvoiceStatus(StrEnum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"  # immutable snapshot; corrections only by reversal (void)
    VOIDED = "VOIDED"  # reversed by a financial_adjustment (issued) or abandoned (draft)


class HirePaymentMethod(StrEnum):
    CASH = "CASH"
    BANK = "BANK"
    MOBILE_MONEY = "MOBILE_MONEY"


class SettlementStatus(StrEnum):
    """Claimed money is evidence of intent only; only VERIFIED settlement reduces balances."""

    CLAIMED = "CLAIMED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class AdjustmentKind(StrEnum):
    INVOICE_REVERSAL = "INVOICE_REVERSAL"


class CustodyEntryType(StrEnum):
    OPENING_BALANCE = "OPENING_BALANCE"  # cash already held when custody tracking starts
    FLOAT_ISSUED = "FLOAT_ISSUED"  # office -> supervisor


class TenantHireInvoice(UuidPk, Base):
    __tablename__ = "tenant_hire_invoice"
    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_number", name="uq_hire_invoice_number"),
        CheckConstraint("(issued_at IS NULL) = (invoice_number IS NULL)", name="ck_hire_invoice_numbered"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[HireInvoiceStatus] = mapped_column(_enum(HireInvoiceStatus), nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(Text)


class HireInvoiceLine(UuidPk, Base):
    """Snapshot of the job's computed charges. Immutable after insert (trigger + no UPDATE/DELETE grant)."""

    __tablename__ = "hire_invoice_line"
    __table_args__ = (UniqueConstraint("invoice_id", "line_no", name="uq_hire_invoice_line_no"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant_hire_invoice.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[ChargeKind] = mapped_column(_enum(ChargeKind), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class HireInvoiceJob(UuidPk, Base):
    """A job's claim on an invoice. The partial unique index makes double invoicing impossible at the database:
    a job can sit on at most one non-voided invoice; voiding releases the claim (only `released_at` may change)."""

    __tablename__ = "hire_invoice_job"
    __table_args__ = (
        Index("uq_hire_invoice_job_active", "job_id", unique=True, postgresql_where=text("released_at IS NULL")),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant_hire_invoice.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HireInvoiceCounter(Base):
    """Per-tenant, per-year gap-free invoice counter (row lock via INSERT .. ON CONFLICT DO UPDATE)."""

    __tablename__ = "hire_invoice_counter"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False)


class FinancialAdjustment(UuidPk, Base):
    """Append-only correction (credit) against a customer's receivable, e.g. the reversal of a voided invoice."""

    __tablename__ = "financial_adjustment"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_fin_adjustment_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant_hire_invoice.id"))
    kind: Mapped[AdjustmentKind] = mapped_column(_enum(AdjustmentKind), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CustomerPayment(UuidPk, Base):
    """Money received from a customer (cash collection, bank or mobile money). Unallocated verified money is
    customer credit (deposit/advance)."""

    __tablename__ = "customer_payment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_customer_payment_client"),
        UniqueConstraint("tenant_id", "method", "reference", name="uq_customer_payment_reference"),
        CheckConstraint("amount > 0", name="ck_customer_payment_amount"),
        CheckConstraint("method = 'CASH' OR reference IS NOT NULL", name="ck_customer_payment_reference"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    method: Mapped[HirePaymentMethod] = mapped_column(_enum(HirePaymentMethod), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"), index=True)
    status: Mapped[SettlementStatus] = mapped_column(_enum(SettlementStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # API | SYNC
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class HirePaymentAllocation(UuidPk, Base):
    """Applies (part of) a payment to an issued invoice. Counts toward the invoice only once the payment is
    VERIFIED; released (never deleted) when the payment is rejected or the invoice is voided."""

    __tablename__ = "hire_payment_allocation"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_hire_allocation_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_payment.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant_hire_invoice.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


class SupervisorCashCustody(UuidPk, Base):
    """Append-only custody movements from the office to a supervisor (floats). Collections, cash-paid expenses
    and handovers live in their own tables and are folded into the custody ledger/reconciliation."""

    __tablename__ = "supervisor_cash_custody"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_custody_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    entry_type: Mapped[CustodyEntryType] = mapped_column(_enum(CustodyEntryType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CashHandover(UuidPk, Base):
    """Supervisor -> office cash handover: CLAIMED by the supervisor until an accountant verifies receipt."""

    __tablename__ = "cash_handover"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_cash_handover_client"),
        CheckConstraint("amount > 0", name="ck_cash_handover_amount"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    handed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SettlementStatus] = mapped_column(_enum(SettlementStatus), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
