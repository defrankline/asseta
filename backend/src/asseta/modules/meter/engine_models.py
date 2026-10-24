"""Engine-hour accountability records (design B): approved meter baselines, tenant-defined explanation lists,
classifications of unallocated engine hours and two-person reading corrections.

The engine-hour ledger itself is *derived* from immutable meter readings on every read (never a stored balance,
[3.4.6]); only human decisions are stored here. Every table is append-only except for the decision stamps of a
PROPOSED row (DB guard triggers), so history is never rewritten ([3.4.1], [3.4.5])."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable
from asseta.modules.meter.models import READING


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class MeterProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"  # waiting for a second person's decision
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BaselineSource(StrEnum):
    CAPTURE = "CAPTURE"  # a reading taken for the purpose (photo/GPS evidence on the proposal)
    READING = "READING"  # proposed from an existing meter reading of the machine (e.g. its earliest)


class EngineHourReasonKind(StrEnum):
    NON_CUSTOMER_CATEGORY = "NON_CUSTOMER_CATEGORY"  # approved non-customer activity (maintenance, relocation ...)
    VARIANCE_REASON = "VARIANCE_REASON"  # identified variance (meter fault, reading error ...)


class ClassificationOutcome(StrEnum):
    APPROVED_NON_CUSTOMER = "APPROVED_NON_CUSTOMER"
    IDENTIFIED_VARIANCE = "IDENTIFIED_VARIANCE"


OUTCOME_REASON_KIND = {
    ClassificationOutcome.APPROVED_NON_CUSTOMER: EngineHourReasonKind.NON_CUSTOMER_CATEGORY,
    ClassificationOutcome.IDENTIFIED_VARIANCE: EngineHourReasonKind.VARIANCE_REASON,
}


class MachineMeterBaseline(UuidPk, Base):
    """The approved, verified initial engine-hour reading of a machine [3.2.1]. One APPROVED baseline per machine
    (re-baselining goes through the meter-reset flow); proposer and approver are different people."""

    __tablename__ = "machine_meter_baseline"
    __table_args__ = (
        Index(
            "uq_meter_baseline_approved",
            "tenant_id",
            "machine_id",
            unique=True,
            postgresql_where=text("status = 'APPROVED'"),
        ),
        Index(
            "uq_meter_baseline_proposed",
            "tenant_id",
            "machine_id",
            unique=True,
            postgresql_where=text("status = 'PROPOSED'"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[BaselineSource] = mapped_column(_enum(BaselineSource, 16), nullable=False)
    source_capture_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meter_capture.id"))
    photo_attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("capture_attachment.id"))
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    accuracy_m: Mapped[float | None] = mapped_column()
    device_id: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MeterProposalStatus] = mapped_column(_enum(MeterProposalStatus, 16), nullable=False)
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # null: proposed by the system
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class EngineHourReason(UuidPk, Deactivatable, Timestamps, Base):
    """Tenant-defined list entry: a non-customer activity category or an identified-variance reason. Business
    data, never an enum; deactivated entries stay on past classifications."""

    __tablename__ = "engine_hour_reason"
    __table_args__ = (UniqueConstraint("tenant_id", "kind", "code", name="uq_engine_hour_reason_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    kind: Mapped[EngineHourReasonKind] = mapped_column(_enum(EngineHourReasonKind, 32), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class EngineHourClassification(UuidPk, Base):
    """A human explanation of one UNALLOCATED ledger segment, identified by its two boundary points (meter
    readings or the baseline) with the hours snapshot at proposal time [3.2.6]. A segment whose boundaries later
    change (a correction or a late reading splits it) no longer matches and shows UNEXPLAINED again: an old
    explanation is never stretched over different hours."""

    __tablename__ = "engine_hour_classification"
    __table_args__ = (
        Index(
            "uq_engine_hour_classification_live",
            "tenant_id",
            "machine_id",
            "start_ref",
            "end_ref",
            unique=True,
            postgresql_where=text("status IN ('PROPOSED', 'APPROVED')"),
        ),
        Index("ix_engine_hour_classification_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    start_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    end_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hours: Mapped[Decimal] = mapped_column(READING, nullable=False)
    outcome: Mapped[ClassificationOutcome] = mapped_column(_enum(ClassificationOutcome, 32), nullable=False)
    reason_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engine_hour_reason.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MeterProposalStatus] = mapped_column(_enum(MeterProposalStatus, 16), nullable=False)
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)


class MeterCorrection(UuidPk, Base):
    """A proposed supersession of a meter reading [3.2.9]: the replacement reading (with its own evidence) is held
    here until a second person approves; only then is the old reading SUPERSEDED and the replacement recorded
    (`replacement_capture_id` is the replacement's device-generated id)."""

    __tablename__ = "meter_correction"
    __table_args__ = (
        Index(
            "uq_meter_correction_open",
            "tenant_id",
            "superseded_capture_id",
            unique=True,
            postgresql_where=text("status = 'PROPOSED'"),
        ),
        Index("ix_meter_correction_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"))
    superseded_capture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_capture.id"), nullable=False)
    replacement_capture_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    replacement: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # the replacement reading payload
    old_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    new_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MeterProposalStatus] = mapped_column(_enum(MeterProposalStatus, 16), nullable=False)
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
