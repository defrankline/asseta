"""Machine reports (ADR-008 §2): a supervisor accounts for every engine hour of a machine assigned to them, from the
machine's last approved reading to a new one, split across customers (hours they bought) and non-productive reasons.

Append-only in the database (guard triggers, migration mrep01): a report's only change is its single decision
(SUBMITTED -> APPROVED | REJECTED with the decision stamps); its lines never change. A rejected report is corrected by
a new report on the same reading (`corrects_id`). At most one SUBMITTED report per machine, and one live (SUBMITTED or
APPROVED) report per reading."""

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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.meter.models import READING


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class MachineReportStatus(StrEnum):
    SUBMITTED = "SUBMITTED"  # customer hours reserved; waiting for a decision
    APPROVED = "APPROVED"  # hours consumed, allocation ledger written, the reading is the machine's last approved one
    REJECTED = "REJECTED"  # reservation released; correct it with a new report on the same reading


class ReportLineKind(StrEnum):
    CUSTOMER = "CUSTOMER"  # hours a customer used (drawn from the hours they bought)
    NON_PRODUCTIVE = "NON_PRODUCTIVE"  # hours no customer pays for, with a reason from the tenant's list and a note


class StartSource(StrEnum):
    """Where the report's previous reading comes from."""

    REPORT = "REPORT"  # the end reading of the machine's last approved report
    BASELINE = "BASELINE"  # the machine's approved meter baseline
    RESET = "RESET"  # the new reading of an approved meter reset (after the last approved reading)
    OPENING = "OPENING"  # an opening report: the machine had no starting reading; this reading becomes it


class MachineReport(UuidPk, Base):
    """MR-<yyyy>-<nnnnn>. `id` may be device-generated (the offline operation id), so a retry never adds a second."""

    __tablename__ = "machine_report"
    __table_args__ = (
        UniqueConstraint("tenant_id", "report_number", name="uq_machine_report_number"),
        Index(
            "uq_machine_report_submitted",
            "tenant_id",
            "machine_id",
            unique=True,
            postgresql_where=text("status = 'SUBMITTED'"),
        ),
        Index(
            "uq_machine_report_reading",
            "capture_id",
            unique=True,
            postgresql_where=text("status IN ('SUBMITTED', 'APPROVED')"),
        ),
        Index("ix_machine_report_machine", "tenant_id", "machine_id", "submitted_at"),
        Index("ix_machine_report_status", "tenant_id", "status"),
        CheckConstraint(
            "(opening AND hours = 0 AND start_reading = end_reading) OR "
            "(NOT opening AND hours > 0 AND end_reading - start_reading = hours)",
            name="ck_machine_report_range",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    report_number: Mapped[str] = mapped_column(String(32), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    capture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_capture.id"), nullable=False)
    start_source: Mapped[StartSource] = mapped_column(_enum(StartSource, 16), nullable=False)
    start_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # report, baseline or reset id
    start_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meter_epoch: Mapped[int] = mapped_column(Integer, nullable=False)  # approved resets at or before start_at
    hours: Mapped[Decimal] = mapped_column(READING, nullable=False)
    # An opening report (no lines, 0 hours): the machine had no approved reading or baseline yet; once approved its
    # reading is where the next report starts.
    opening: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    status: Mapped[MachineReportStatus] = mapped_column(_enum(MachineReportStatus, 16), nullable=False)
    corrects_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine_report.id"), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(8), nullable=False)  # API | SYNC
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MachineReportLine(UuidPk, Base):
    """One part of the report's hours: a customer's hours or non-productive hours with a reason and a note."""

    __tablename__ = "machine_report_line"
    __table_args__ = (
        UniqueConstraint("report_id", "line_no", name="uq_machine_report_line_no"),
        CheckConstraint("hours > 0", name="ck_machine_report_line_hours"),
        CheckConstraint(
            "(kind = 'CUSTOMER' AND customer_id IS NOT NULL AND reason_id IS NULL) OR "
            "(kind = 'NON_PRODUCTIVE' AND customer_id IS NULL AND reason_id IS NOT NULL AND note IS NOT NULL)",
            name="ck_machine_report_line_kind",
        ),
        Index("ix_machine_report_line_customer", "tenant_id", "customer_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine_report.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[ReportLineKind] = mapped_column(_enum(ReportLineKind, 16), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id"))
    reason_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("engine_hour_reason.id"))
    hours: Mapped[Decimal] = mapped_column(READING, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
