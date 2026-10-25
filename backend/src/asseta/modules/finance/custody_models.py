"""Cash custody chain controls (accountability design C): field-to-field transfers, float acknowledgements,
variances, approved retentions, custody adjustments and the tenant's own reason lists.

Every table is tenant-owned (FORCE RLS). Evidence is append-only or guarded by triggers so that only a single,
recorded decision can change a row; corrections are new rows (adjustments), never edits."""

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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, SyncRevisioned, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable
from asseta.modules.finance.models import MONEY


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class CashTransferStatus(StrEnum):
    PENDING_ACKNOWLEDGEMENT = "PENDING_ACKNOWLEDGEMENT"  # in transit: still in the sender's custody
    ACKNOWLEDGED = "ACKNOWLEDGED"  # the receiver confirmed the amount actually received
    DISPUTED = "DISPUTED"  # the receiver did not confirm; nothing moved


class AcknowledgementMethod(StrEnum):
    RECEIVER = "RECEIVER"  # the receiving custodian (own login) acknowledged
    ON_BEHALF = "ON_BEHALF"  # a recorder acknowledged for a receiving custodian (policy)
    RECORDER_IS_RECEIVER = "RECORDER_IS_RECEIVER"  # the recorder of the transfer is the receiver (policy)
    NOT_REQUIRED = "NOT_REQUIRED"  # the tenant does not require acknowledgement (policy)


class VarianceSource(StrEnum):
    TRANSFER = "TRANSFER"
    REMITTANCE = "REMITTANCE"
    FLOAT = "FLOAT"


class VarianceStatus(StrEnum):
    OPEN = "OPEN"
    WRITE_OFF_PROPOSED = "WRITE_OFF_PROPOSED"
    RESOLVED = "RESOLVED"


class VarianceOutcome(StrEnum):
    RECOVERED = "RECOVERED"
    CORRECTED_ERROR = "CORRECTED_ERROR"
    WRITTEN_OFF = "WRITTEN_OFF"


class CashReasonKind(StrEnum):
    """Which tenant list a reason belongs to (the reasons themselves are tenant data)."""

    VARIANCE = "VARIANCE"
    WRITE_OFF = "WRITE_OFF"
    RETENTION = "RETENTION"
    ADJUSTMENT = "ADJUSTMENT"


class CustodyAdjustmentKind(StrEnum):
    REVERSAL = "REVERSAL"  # undoes a recorded movement
    ADJUSTMENT = "ADJUSTMENT"  # corrects the expected balance


class CashDecisionStatus(StrEnum):
    """Single decision lifecycle (guard_pending_decision): PENDING -> APPROVED | REJECTED."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CashReason(UuidPk, Deactivatable, Timestamps, Base):
    """A tenant-defined reason (variance, write-off, retention, adjustment). Lists are business data, not enums."""

    __tablename__ = "cash_reason"
    __table_args__ = (
        Index("uq_cash_reason_label", "tenant_id", "kind", text("lower(label)"), unique=True),
        CheckConstraint("char_length(label) >= 2", name="ck_cash_reason_label"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    kind: Mapped[CashReasonKind] = mapped_column(_enum(CashReasonKind), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class CashTransfer(UuidPk, SyncRevisioned, Base):
    """Field-to-field cash transfer. Never a company receipt: it only moves accountability between custodians, and
    only once acknowledged (the acknowledged amount moves; any difference stays with the sender as a variance)."""

    __tablename__ = "cash_transfer"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_cash_transfer_client"),
        CheckConstraint("amount_declared > 0", name="ck_cash_transfer_amount"),
        CheckConstraint("amount_received IS NULL OR amount_received >= 0", name="ck_cash_transfer_received"),
        CheckConstraint("from_staff_id <> to_staff_id", name="ck_cash_transfer_parties"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    from_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    to_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    amount_declared: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    transferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CashTransferStatus] = mapped_column(_enum(CashTransferStatus), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(80))
    amount_received: Mapped[Decimal | None] = mapped_column(MONEY)
    ack_method: Mapped[AcknowledgementMethod | None] = mapped_column(_enum(AcknowledgementMethod))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ack_note: Mapped[str | None] = mapped_column(Text)


class CashFloatAcknowledgement(UuidPk, Base):
    """The receiver's acknowledgement (or dispute) of an office float that required one. Append-only, one per float."""

    __tablename__ = "cash_float_acknowledgement"
    __table_args__ = (
        UniqueConstraint("custody_entry_id", name="uq_cash_float_ack_entry"),
        UniqueConstraint("tenant_id", "client_id", name="uq_cash_float_ack_client"),
        CheckConstraint("amount_received >= 0", name="ck_cash_float_ack_amount"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    custody_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supervisor_cash_custody.id"), nullable=False)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    disputed: Mapped[bool] = mapped_column(nullable=False)
    amount_received: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # 0 when disputed
    method: Mapped[AcknowledgementMethod] = mapped_column(_enum(AcknowledgementMethod), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CashVariance(UuidPk, Base):
    """Declared != received on a transfer, remittance or float. Neutral: a difference to explain, not a verdict.
    `amount` = declared - received (negative = more received than declared). `staff_member_id` is the custodian who
    stays accountable for the difference (null for floats: the difference sits with the office). Only a write-off
    changes custody (by -amount on that custodian)."""

    __tablename__ = "cash_variance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_type", "source_id", name="uq_cash_variance_source"),
        CheckConstraint("amount <> 0", name="ck_cash_variance_amount"),
        CheckConstraint("(status = 'RESOLVED') = (outcome IS NOT NULL)", name="ck_cash_variance_outcome"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    source_type: Mapped[VarianceSource] = mapped_column(_enum(VarianceSource), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    staff_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"), index=True)
    counterparty_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"))
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    declared_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    received_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anomaly_case.id"))
    policy_version: Mapped[str | None] = mapped_column(String(80))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # the decision that produced it
    status: Mapped[VarianceStatus] = mapped_column(_enum(VarianceStatus), nullable=False)
    reason_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cash_reason.id"))
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposal_note: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[VarianceOutcome | None] = mapped_column(_enum(VarianceOutcome))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)


class CashRetention(UuidPk, Base):
    """Authorised exception to full remittance: the custodian may keep up to `amount` until `valid_until`."""

    __tablename__ = "cash_retention"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_cash_retention_amount"),
        UniqueConstraint("tenant_id", "client_id", name="uq_cash_retention_client"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # offline idempotency (sync op)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    reason_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cash_reason.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[CashDecisionStatus] = mapped_column(_enum(CashDecisionStatus), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class CustodyAdjustment(UuidPk, Base):
    """Authorised correction of a custodian's expected balance (signed: positive raises it). Proposed by one person,
    approved by another; counts only once APPROVED."""

    __tablename__ = "custody_adjustment"
    __table_args__ = (CheckConstraint("amount <> 0", name="ck_custody_adjustment_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    kind: Mapped[CustodyAdjustmentKind] = mapped_column(_enum(CustodyAdjustmentKind), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cash_reason.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reverses_entity_type: Mapped[str | None] = mapped_column(String(40))
    reverses_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[CashDecisionStatus] = mapped_column(_enum(CashDecisionStatus), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class RemittanceOverdue(UuidPk, Base):
    """A custodian still holding unremitted cash (beyond approved retentions) after the tenant's daily remittance
    cut-off (`cash.remittance_cutoff_hour`, tenant-local). One row per custodian per tenant-local day (the sweep is
    idempotent); append-only evidence: `amounts` is what was held, per currency, when the sweep flagged it."""

    __tablename__ = "cash_remittance_overdue"
    __table_args__ = (
        UniqueConstraint("tenant_id", "staff_member_id", "local_day", name="uq_cash_remittance_overdue_day"),
        CheckConstraint("cutoff_hour BETWEEN 0 AND 23", name="ck_cash_remittance_overdue_hour"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    local_day: Mapped[date] = mapped_column(Date, nullable=False)
    cutoff_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    amounts: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)  # [{currency, amount}]
    flagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
