"""Customer hours tables. Balances are never stored: they are derived from the append-only `hours_ledger_entry`.
Purchases are immutable after creation (only the cancellation stamp may be set, once); approvals are separate rows
with a single decision; reason lists are tenant data. Database guards (migration hrssec000001) enforce all of it."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
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
from asseta.core.lifecycle import Deactivatable

MONEY = Numeric(18, 4)
HOURS = Numeric(12, 2)
PERCENT = Numeric(7, 4)


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class ReasonKind(StrEnum):
    """Which tenant reason list an entry belongs to (the entries themselves are tenant data)."""

    DISCOUNT = "DISCOUNT"
    CREDIT = "CREDIT"
    TRANSFER = "TRANSFER"
    CANCELLATION = "CANCELLATION"


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"  # the proposer took it back before a decision
    REVOKED = "REVOKED"  # an approved arrangement ended early (audited, reason)


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"  # applied (ledger entries written)
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class LedgerEntryType(StrEnum):
    ACTIVATED = "ACTIVATED"  # + hours become usable (verified payment or authorised credit)
    CONSUMED = "CONSUMED"  # - work execution allocation of a completed job
    TRANSFER_OUT = "TRANSFER_OUT"  # - approved move to another machine
    TRANSFER_IN = "TRANSFER_IN"  # + the receiving machine
    EXPIRED = "EXPIRED"  # - unused activated hours past the tenant expiry period
    REVERSAL = "REVERSAL"  # - activated hours withdrawn (approved cancellation)
    # Daily drawdown (DEC-031 P1, policy CUSTOMER_HOURS.drawdown = DAILY): a running prepaid job's customer-work hours
    # of one tenant-local day (`usage_day`), drawn provisionally; PROVISIONAL_REVERSED gives them back (a corrected
    # reading, a cancelled job, or the final work execution allocation at completion, which then consumes the job's
    # billable hours as CONSUMED). Provisional minus reversed is what running jobs currently hold.
    PROVISIONAL = "PROVISIONAL"  # -
    PROVISIONAL_REVERSED = "PROVISIONAL_REVERSED"  # +


class ActivationSource(StrEnum):
    PAYMENT = "PAYMENT"
    CREDIT = "CREDIT"


SIGN: dict[LedgerEntryType, int] = {
    LedgerEntryType.ACTIVATED: 1,
    LedgerEntryType.TRANSFER_IN: 1,
    LedgerEntryType.CONSUMED: -1,
    LedgerEntryType.TRANSFER_OUT: -1,
    LedgerEntryType.EXPIRED: -1,
    LedgerEntryType.REVERSAL: -1,
    LedgerEntryType.PROVISIONAL: -1,
    LedgerEntryType.PROVISIONAL_REVERSED: 1,
}


class HoursSequence(Base):
    """Gap-free per-tenant counters (row lock via INSERT .. ON CONFLICT DO UPDATE): `HP` per year, `WALK` (year 0)."""

    __tablename__ = "hours_sequence"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    series: Mapped[str] = mapped_column(String(8), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False)


class HoursReasonCode(UuidPk, Deactivatable, Base):
    """Tenant-maintained reason list entries (discount reasons, credit terms, transfer/cancellation reasons)."""

    __tablename__ = "hours_reason_code"
    __table_args__ = (UniqueConstraint("tenant_id", "kind", "code", name="uq_hours_reason_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    kind: Mapped[ReasonKind] = mapped_column(_enum(ReasonKind, 16), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class CustomerDiscount(UuidPk, Base):
    """A predefined, authorised customer discount. Only APPROVED discounts in effect apply, automatically."""

    __tablename__ = "customer_discount"
    __table_args__ = (
        CheckConstraint("percent > 0 AND percent <= 100", name="ck_customer_discount_percent"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_customer_discount_dates"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    percent: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_reason_code.id"))
    status: Mapped[ProposalStatus] = mapped_column(_enum(ProposalStatus, 16), nullable=False)
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class CreditArrangement(UuidPk, Base):
    """Per-customer credit limit (money). Exposure = credit-activated value not yet covered by verified payments."""

    __tablename__ = "credit_arrangement"
    __table_args__ = (
        CheckConstraint("limit_amount > 0", name="ck_credit_arrangement_limit"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_credit_arrangement_dates"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    limit_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    terms: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_reason_code.id"))
    status: Mapped[ProposalStatus] = mapped_column(_enum(ProposalStatus, 16), nullable=False)
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class HoursPurchase(UuidPk, Base):
    """HP-<yyyy>-<nnnnn>: hours bought for one specific machine at the rate card price less the approved discount.
    Immutable after creation; the only later change is the cancellation stamp (guard trigger)."""

    __tablename__ = "hours_purchase"
    __table_args__ = (
        UniqueConstraint("tenant_id", "purchase_number", name="uq_hours_purchase_number"),
        UniqueConstraint("tenant_id", "client_id", name="uq_hours_purchase_client"),
        CheckConstraint("hours > 0", name="ck_hours_purchase_hours"),
        CheckConstraint("amount >= 0 AND hourly_rate >= 0 AND effective_rate >= 0", name="ck_hours_purchase_money"),
        Index("ix_hours_purchase_customer_machine", "tenant_id", "customer_id", "machine_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    purchase_number: Mapped[str] = mapped_column(String(32), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    job_site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_site.id"))
    hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    rate_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rental_rate_policy.id"), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_discount.id"))
    discount_percent: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    effective_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # hourly_rate x (1 - discount)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # hours x effective_rate (currency minor units)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # API | SYNC
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    cancellation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class HoursPaymentAllocation(UuidPk, Base):
    """Links (part of) a customer payment to an hours purchase. Activates hours only once the payment is VERIFIED;
    released (never deleted) when the payment is rejected or the purchase is cancelled before use."""

    __tablename__ = "hours_payment_allocation"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_hours_allocation_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_payment.id"), nullable=False, index=True)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hours_purchase.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


class PaymentEvidence(UuidPk, Base):
    """Receipt photo / mobile-money screenshot attached to a payment. Evidence only: never verifies anything."""

    __tablename__ = "payment_evidence"
    __table_args__ = (UniqueConstraint("payment_id", "attachment_id", name="uq_payment_evidence"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_payment.id"), nullable=False, index=True)
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("capture_attachment.id"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WorkExecutionAllocation(UuidPk, Base):
    """One per prepaid job, written on COMPLETE: the job's billable hours. What was actually consumed is the sum of
    its CONSUMED ledger entries; the rest is the overrun (HOURS_OVERRUN exception) until covered or reviewed."""

    __tablename__ = "work_execution_allocation"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_work_execution_allocation_job"),
        CheckConstraint("billable_hours >= 0", name="ck_wea_hours"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    billable_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    exception_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_exception.id"))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class HoursTransfer(UuidPk, Base):
    """Move remaining hours of a purchase from one machine to another (the purchase keeps its original machine)."""

    __tablename__ = "hours_transfer"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_hours_transfer_client"),
        CheckConstraint("hours > 0", name="ck_hours_transfer_hours"),
        CheckConstraint("from_machine_id <> to_machine_id", name="ck_hours_transfer_machines"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hours_purchase.id"), nullable=False, index=True)
    from_machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False)
    to_machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False)
    hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_reason_code.id"))
    status: Mapped[RequestStatus] = mapped_column(_enum(RequestStatus, 16), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class HoursCancellation(UuidPk, Base):
    """Cancellation of a purchase (reason + approver per policy): reverses the remaining activated hours."""

    __tablename__ = "hours_cancellation"
    __table_args__ = (
        Index(
            "uq_hours_cancellation_pending",
            "purchase_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'APPROVED')"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hours_purchase.id"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_reason_code.id"))
    status: Mapped[RequestStatus] = mapped_column(_enum(RequestStatus, 16), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class HoursLedgerEntry(UuidPk, Base):
    """Append-only (trigger + no UPDATE/DELETE grant). `hours` is always positive; the entry type gives the sign."""

    __tablename__ = "hours_ledger_entry"
    __table_args__ = (
        CheckConstraint("hours > 0", name="ck_hours_ledger_hours"),
        CheckConstraint(
            "(entry_type = 'ACTIVATED') = (activation_source IS NOT NULL)", name="ck_hours_ledger_activation"
        ),
        Index("ix_hours_ledger_purchase", "purchase_id", "occurred_at"),
        Index("ix_hours_ledger_customer_machine", "tenant_id", "customer_id", "machine_id"),
        Index("ix_hours_ledger_job_type", "job_id", "entry_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hours_purchase.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    entry_type: Mapped[LedgerEntryType] = mapped_column(_enum(LedgerEntryType, 24), nullable=False)
    hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activation_source: Mapped[ActivationSource | None] = mapped_column(_enum(ActivationSource, 16))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ACTIVATED lots only
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_payment.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"), index=True)
    allocation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_execution_allocation.id"), index=True)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_transfer.id"))
    cancellation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hours_cancellation.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    policy_version: Mapped[str | None] = mapped_column(String(80))
    usage_day: Mapped[date | None] = mapped_column(Date)  # PROVISIONAL / PROVISIONAL_REVERSED: the tenant-local day
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class HoursLowBalanceAlert(UuidPk, Base):
    """One low-balance crossing of a purchase (DEC-031 P2, `CUSTOMER_HOURS.low_balance_hours`): written when the
    purchase's remaining hours (and the customer's hours left on that machine) fall to the threshold, re-armed when
    the purchase is back above it. At most one armed alert per purchase, so the office (and, when the tenant
    switches it on, the customer by SMS) is told once per crossing."""

    __tablename__ = "hours_low_balance_alert"
    __table_args__ = (
        UniqueConstraint("purchase_id", "sequence", name="uq_hours_low_balance_alert_sequence"),
        Index(
            "uq_hours_low_balance_alert_armed",
            "purchase_id",
            unique=True,
            postgresql_where=text("rearmed_at IS NULL"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hours_purchase.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    remaining_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)  # purchase remaining when it crossed
    available_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)  # customer's hours left on the machine
    crossed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notify_customer: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # customer SMS: NOT_REQUESTED | PENDING | QUEUED | NO_PHONE
    customer_sms_status: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_sms_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    rearmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
