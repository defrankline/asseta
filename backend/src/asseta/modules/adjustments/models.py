"""Ledger 6 (guideline 4.6, DEC-032 B1): every activity that changes an otherwise established customer, operational or
financial balance. `adjustment_ledger_entry` is append-only: one row per decided adjustment (the original transaction,
the type, original/new value or amount, reason, evidence, requester, approver, timestamps, resulting balance).
`adjustment_request` is the uniform propose/decide flow for the new reversible actions (customer-hour corrections,
refunds, reversals of posted transactions, invoice voids); the existing approval flows keep their own request tables
and post to the ledger when decided."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow

MONEY = Numeric(18, 4)
HOURS = Numeric(14, 2)
VALUE = Numeric(18, 4)  # hours, a meter reading or money, per `unit`


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class AdjustmentType(StrEnum):
    """What kind of change the ledger entry records (guideline 4.6). Stable contract values."""

    HOURS_TRANSFER = "HOURS_TRANSFER"
    HOURS_CANCELLATION = "HOURS_CANCELLATION"
    HOURS_CORRECTION = "HOURS_CORRECTION"
    HOURS_REFUND = "HOURS_REFUND"
    CREDIT_ARRANGEMENT = "CREDIT_ARRANGEMENT"
    METER_CORRECTION = "METER_CORRECTION"
    ALLOCATION_CORRECTION = "ALLOCATION_CORRECTION"
    ENGINE_HOUR_CLASSIFICATION = "ENGINE_HOUR_CLASSIFICATION"
    NON_REVENUE_APPROVAL = "NON_REVENUE_APPROVAL"
    CASH_WRITE_OFF = "CASH_WRITE_OFF"
    CASH_VARIANCE_RESOLUTION = "CASH_VARIANCE_RESOLUTION"
    CUSTODY_ADJUSTMENT = "CUSTODY_ADJUSTMENT"
    INVOICE_VOID = "INVOICE_VOID"
    PAYMENT_REVERSAL = "PAYMENT_REVERSAL"
    COLLECTION_REVERSAL = "COLLECTION_REVERSAL"
    PURCHASE_REVERSAL = "PURCHASE_REVERSAL"


class AdjustmentRequestType(StrEnum):
    """The new reversible actions handled by the uniform propose/decide flow."""

    HOURS_CORRECTION = "HOURS_CORRECTION"
    HOURS_REFUND = "HOURS_REFUND"
    PAYMENT_REVERSAL = "PAYMENT_REVERSAL"
    COLLECTION_REVERSAL = "COLLECTION_REVERSAL"
    PURCHASE_REVERSAL = "PURCHASE_REVERSAL"
    INVOICE_VOID = "INVOICE_VOID"


class AdjustmentEntryStatus(StrEnum):
    APPROVED = "APPROVED"  # the adjustment took effect
    REJECTED = "REJECTED"  # declined; retained so the approval history is complete (no balance changed)
    REVOKED = "REVOKED"  # an approved arrangement ended early


class AdjustmentRequestStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class AdjustmentUnit(StrEnum):
    HOURS = "HOURS"
    MONEY = "MONEY"
    READING = "READING"


class RefundSettlement(StrEnum):
    CREDIT = "CREDIT"  # the money returns to the customer's unallocated credit
    PAY_OUT = "PAY_OUT"  # the money is paid back to the customer


class AdjustmentLedgerEntry(UuidPk, Base):
    """One decided adjustment. Insert-only (guard trigger, no UPDATE/DELETE grant, FORCE RLS)."""

    __tablename__ = "adjustment_ledger_entry"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_type", "source_id", "status", name="uq_adjustment_entry_source"),
        Index("ix_adjustment_entry_type", "tenant_id", "adjustment_type", "posted_at"),
        Index("ix_adjustment_entry_posted", "tenant_id", "posted_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    adjustment_type: Mapped[AdjustmentType] = mapped_column(_enum(AdjustmentType, 32), nullable=False)
    status: Mapped[AdjustmentEntryStatus] = mapped_column(_enum(AdjustmentEntryStatus, 16), nullable=False)
    # What was adjusted, as recorded.
    original_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    original_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    # The record that carried the adjustment (a transfer, a request, ...): one entry per record and outcome.
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    unit: Mapped[AdjustmentUnit] = mapped_column(_enum(AdjustmentUnit, 16), nullable=False)
    original_value: Mapped[Decimal | None] = mapped_column(VALUE)
    new_value: Mapped[Decimal | None] = mapped_column(VALUE)
    amount: Mapped[Decimal | None] = mapped_column(VALUE)  # signed change (hours or money); null when not a quantity
    currency: Mapped[str | None] = mapped_column(String(3))
    resulting_balance: Mapped[Decimal | None] = mapped_column(VALUE)  # the affected balance after this adjustment
    # Tenant reason list reference and the words used when it was decided.
    reason_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason_label: Mapped[str | None] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_attachment_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    # Filterable subjects (names are resolved for display).
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id"), index=True)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine.id"), index=True)
    staff_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"), index=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(80))
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AdjustmentRequest(UuidPk, Base):
    """A proposed reversible action: one person proposes, another decides (always, never relaxable). The proposal's
    content is immutable; only the single decision may change the row (guard trigger)."""

    __tablename__ = "adjustment_request"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_adjustment_request_client"),
        # A posted transaction is reversed at most once: one live or approved reversal per original record.
        Index(
            "uq_adjustment_request_reversal",
            "tenant_id",
            "original_type",
            "original_id",
            unique=True,
            postgresql_where=text(
                "status IN ('PROPOSED', 'APPROVED') AND request_type IN "
                "('PAYMENT_REVERSAL', 'COLLECTION_REVERSAL', 'PURCHASE_REVERSAL', 'INVOICE_VOID')"
            ),
        ),
        CheckConstraint("hours IS NULL OR hours <> 0", name="ck_adjustment_request_hours"),
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_adjustment_request_amount"),
        Index("ix_adjustment_request_status", "tenant_id", "status", "proposed_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_type: Mapped[AdjustmentRequestType] = mapped_column(_enum(AdjustmentRequestType, 32), nullable=False)
    status: Mapped[AdjustmentRequestStatus] = mapped_column(_enum(AdjustmentRequestStatus, 16), nullable=False)
    original_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    original_reference: Mapped[str | None] = mapped_column(String(120))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id"), index=True)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine.id"), index=True)
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_purchase.id"), index=True)
    hours: Mapped[Decimal | None] = mapped_column(HOURS)  # signed for corrections
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str | None] = mapped_column(ForeignKey("currency.code"))
    settlement: Mapped[RefundSettlement | None] = mapped_column(_enum(RefundSettlement, 16))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # payout details, the consumed entry, ...
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_reason_code.id"))
    evidence_attachment_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # what the approval did (hours, money, balances)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
