"""Work allocation ledger ("Ledger 3", DEC-032 A1), mid-job changeovers (A3) and the daily operational report (A4).

Append-only in the database: guard triggers allow only a row's status transition and its decision stamps, and the
application role has no DELETE. Correcting an allocation adds new entries that supersede the old one (the original
stays visible). An exclusion constraint refuses overlapping meter ranges among a machine's ACTIVE entries."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.meter.models import READING


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class AllocationKind(StrEnum):
    CUSTOMER_WORK = "CUSTOMER_WORK"
    AUTHORIZED_ACTIVITY = "AUTHORIZED_ACTIVITY"  # approved non-customer activity or identified exception
    UNEXPLAINED = "UNEXPLAINED"  # stays visible until a person's explanation is approved


class AllocationStatus(StrEnum):
    PROPOSED = "PROPOSED"  # a correction awaiting a second person's decision
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"  # replaced; kept for history
    REJECTED = "REJECTED"  # a correction that was refused


class AllocationSource(StrEnum):
    DERIVED = "DERIVED"  # written from the machine's readings
    BACKFILL = "BACKFILL"  # written by the migration from existing history
    CORRECTION = "CORRECTION"  # a person's correction


class DailyReportStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    RETURNED = "RETURNED"
    SUPERSEDED = "SUPERSEDED"


class WorkAllocation(UuidPk, Base):
    """One contiguous meter range of one machine on one tenant-local work day, allocated to a customer or activity
    or left unexplained. `origin_key` ties a correction to the ledger piece it replaced."""

    __tablename__ = "work_allocation"
    __table_args__ = (
        Index("ix_work_allocation_machine_day", "tenant_id", "machine_id", "work_date"),
        Index("ix_work_allocation_customer_day", "tenant_id", "customer_id", "work_date"),
        Index("ix_work_allocation_group", "tenant_id", "correction_group_id"),
        Index("ix_work_allocation_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # a reading or the baseline
    start_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    end_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meter_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # approved resets before this range
    hours: Mapped[Decimal] = mapped_column(READING, nullable=False)
    kind: Mapped[AllocationKind] = mapped_column(_enum(AllocationKind), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"), index=True)
    activity_type: Mapped[str | None] = mapped_column(String(24))  # work-log type of non-revenue time inside a job
    reason_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("engine_hour_reason.id"))  # activity category
    classification_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("engine_hour_classification.id"))
    changeover_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine_changeover.id"))
    reading_review: Mapped[str] = mapped_column(String(16), nullable=False)  # VERIFIED | PENDING_REVIEW
    # The approval behind this entry, where one is required: engine_hour_classification, non_revenue_approval or
    # work_allocation_correction (several work-log entries can share one interval, hence a list).
    approval_ref_type: Mapped[str | None] = mapped_column(String(32))
    approval_ref_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    lots: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)  # {purchase_id, hours}
    evidence_attachment_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    source: Mapped[AllocationSource] = mapped_column(_enum(AllocationSource), nullable=False)
    status: Mapped[AllocationStatus] = mapped_column(_enum(AllocationStatus), nullable=False)
    origin_key: Mapped[str] = mapped_column(String(120), nullable=False)
    origin_hours: Mapped[Decimal] = mapped_column(READING, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_allocation.id"), index=True)
    correction_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    correction_reason: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MachineChangeover(UuidPk, Base):
    """A reading taken during a running job at which the machine moved to another customer (A3). Never touches the
    job's status: the one-active-job-per-machine rule stands. `to_job_id` optionally names the follow-on job."""

    __tablename__ = "machine_changeover"
    __table_args__ = (UniqueConstraint("capture_id", name="uq_machine_changeover_capture"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    capture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_capture.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), nullable=False, index=True)
    from_customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False)
    to_customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False)
    to_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DailyOperationalReport(UuidPk, Base):
    """A machine's report for one tenant-local day (A4). `id` is device-generated, so a retry never adds a second one;
    a genuine repeat for the same machine-day is kept and flagged (DUPLICATE_DAILY_REPORT), never overwritten."""

    __tablename__ = "daily_operational_report"
    __table_args__ = (
        Index("ix_daily_report_machine_date", "tenant_id", "machine_id", "report_date"),
        Index("ix_daily_report_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening_ref: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_capture.id"), nullable=False)
    opening_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    closing_ref: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_capture.id"), nullable=False)
    closing_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    total_hours: Mapped[Decimal] = mapped_column(READING, nullable=False)  # derived from the two readings
    billable_hours: Mapped[Decimal] = mapped_column(READING, nullable=False)
    unbillable_hours: Mapped[Decimal] = mapped_column(READING, nullable=False)
    difference_hours: Mapped[Decimal] = mapped_column(READING, nullable=False)  # total - billable - unbillable
    unbillable: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)  # {reason_id, hours}
    allocations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)  # at submission
    evidence_attachment_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DailyReportStatus] = mapped_column(_enum(DailyReportStatus), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("daily_operational_report.id"))
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("daily_operational_report.id"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(8), nullable=False)  # API | SYNC
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # submitted after the day's cut-off
