"""Revenue reconciliation records (DEC-031 R3): the tenant's reason list and one revenue difference per machine,
period and currency whose money fell short of the expected revenue beyond the tenant's tolerance.

Nothing here duplicates a ledger: expected and attributed amounts are snapshots of a computation over the engine-hour
ledger, jobs, invoices and prepaid allocations, refreshed by the sweep while the difference is still open; only the
human explanation and decision are original data. A decided difference is final (DB guard trigger)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk
from asseta.core.lifecycle import Deactivatable

MONEY = Numeric(18, 4)


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class RevenueDifferenceStatus(StrEnum):
    OPEN = "OPEN"  # a revenue difference to explain
    EXPLANATION_PROPOSED = "EXPLANATION_PROPOSED"  # explained by one person, awaiting another's decision
    EXPLAINED = "EXPLAINED"  # explanation approved by a second person (final)
    CONFIRMED = "CONFIRMED"  # confirmed as a real difference (money to recover / accepted loss; final)
    CLEARED = "CLEARED"  # money arrived later: back within tolerance on a re-check (system; final)


FINAL_STATUSES = (RevenueDifferenceStatus.EXPLAINED, RevenueDifferenceStatus.CONFIRMED, RevenueDifferenceStatus.CLEARED)


class RevenueReason(UuidPk, Deactivatable, Timestamps, Base):
    """Tenant list of reasons that explain a revenue difference (business data, never an enum)."""

    __tablename__ = "revenue_reason"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_revenue_reason_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class RevenueDifference(UuidPk, Base):
    __tablename__ = "revenue_difference"
    __table_args__ = (
        UniqueConstraint("tenant_id", "machine_id", "period_key", "currency", name="uq_revenue_difference_period"),
        Index("ix_revenue_difference_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    period_kind: Mapped[str] = mapped_column(String(8), nullable=False)  # DAY | WEEK | JOB
    period_key: Mapped[str] = mapped_column(String(64), nullable=False)  # DAY:2026-10-25 | WEEK:2026-10-19 | JOB:<id>
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_from: Mapped[date] = mapped_column(Date, nullable=False)  # tenant-local first day of the period
    local_to: Mapped[date] = mapped_column(Date, nullable=False)  # tenant-local last day (inclusive)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"))  # JOB periods
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    in_progress_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    attributed_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    difference: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # expected - in progress - attributed
    customer_work_hours: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    non_revenue_hours: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Engine hours outside jobs not approved as non-customer activity, and the revenue expected from them
    # (part of expected_amount; 0 when the tenant excludes them).
    unexplained_hours: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unexplained_expected_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # jobs and money sources (drill-down)
    status: Mapped[RevenueDifferenceStatus] = mapped_column(_enum(RevenueDifferenceStatus, 24), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anomaly_case.id"))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("revenue_reason.id"))
    explanation_note: Mapped[str | None] = mapped_column(Text)
    explained_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    explained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class RevenueDifferenceAdjustment(UuidPk, Base):
    """A later change to a decided (EXPLAINED / CONFIRMED) difference — e.g. engine hours approved as non-customer
    activity after the decision — recorded alongside it instead of rewriting it (append-only)."""

    __tablename__ = "revenue_difference_adjustment"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    difference_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("revenue_difference.id"), nullable=False, index=True)
    previous_difference: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    new_difference: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # new - previous
    cause_type: Mapped[str] = mapped_column(String(40), nullable=False)  # classification | non_revenue_approval
    cause_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NonRevenueApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"  # explained by one person, awaiting a second person's decision
    APPROVED = "APPROVED"  # counts as non-revenue
    REJECTED = "REJECTED"  # stays revenue (a new explanation may be proposed)


class NonRevenueApproval(UuidPk, Base):
    """[R1, owner 2026-10-26] Explanation and approval of one non-billable work-log entry of a declared non-revenue
    type (e.g. movement to/from a site). Until APPROVED the time counts as revenue. Same flow as engine-hour
    classifications: proposed by one person, decided by another holding `tenant.revenue.decide`."""

    __tablename__ = "non_revenue_approval"
    __table_args__ = (
        Index(
            "uq_non_revenue_approval_live",
            "tenant_id",
            "activity_id",
            unique=True,
            postgresql_where=text("status IN ('PROPOSED', 'APPROVED')"),
        ),
        Index("ix_non_revenue_approval_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_activity.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("revenue_reason.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[NonRevenueApprovalStatus] = mapped_column(_enum(NonRevenueApprovalStatus, 16), nullable=False)
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
