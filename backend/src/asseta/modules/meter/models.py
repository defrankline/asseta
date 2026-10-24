"""Hour-meter evidence (R1-E): captures (immutable, with GPS attempt result and OCR provenance), approved resets,
evidence attachments, and auditable exceptions. Corrections are superseding records, never edits."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
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

from asseta.core.db import Base, SyncRevisioned, UuidPk, utcnow

READING = Numeric(14, 2)


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class ReadingKind(StrEnum):
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    DAILY = "DAILY"  # daily operational reading of a machine, inside or outside a job (job_id optional)


class GpsStatus(StrEnum):
    FIX = "FIX"
    NO_FIX = "NO_FIX"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    DISABLED = "DISABLED"


class CaptureState(StrEnum):
    ACCEPTED = "ACCEPTED"
    PROVISIONAL = "PROVISIONAL"  # accepted for field continuity; open exceptions require review
    REJECTED = "REJECTED"  # stored as evidence, not used for calculations
    SUPERSEDED = "SUPERSEDED"  # replaced by an approved correction


class ExceptionType(StrEnum):
    GPS_UNAVAILABLE = "GPS_UNAVAILABLE"
    GPS_INACCURATE = "GPS_INACCURATE"
    GPS_STALE = "GPS_STALE"
    LOCATION_MISMATCH = "LOCATION_MISMATCH"
    MODE_POLICY_VIOLATION = "MODE_POLICY_VIOLATION"
    PHOTO_MISSING = "PHOTO_MISSING"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    MANUAL_CORRECTION = "MANUAL_CORRECTION"
    METER_DECREASE = "METER_DECREASE"
    IMPOSSIBLE_INCREMENT = "IMPOSSIBLE_INCREMENT"
    CONTINUITY_GAP = "CONTINUITY_GAP"
    DUPLICATE_IMAGE = "DUPLICATE_IMAGE"
    TELEMETRY_MISMATCH = "TELEMETRY_MISMATCH"
    CLOCK_SKEW = "CLOCK_SKEW"
    POLICY_SNAPSHOT_UNVERIFIED = "POLICY_SNAPSHOT_UNVERIFIED"  # offline snapshot not issued to the device / not valid
    # Engine-hour accountability (design B): machine-level flags, raised for review only, never a verdict.
    MISSING_DAILY_REPORT = "MISSING_DAILY_REPORT"  # working machine without a reading by the policy cut-off
    UNEXPLAINED_HOURS = "UNEXPLAINED_HOURS"  # an unallocated engine-hour segment nobody has explained yet
    OVERLAPPING_ALLOCATION = "OVERLAPPING_ALLOCATION"  # two jobs claim the same engine interval
    HOURS_OVERRUN = "HOURS_OVERRUN"  # prepaid job used more hours than the customer had activated on the machine


class ExceptionStatus(StrEnum):
    OPEN = "OPEN"
    EXPLAINED = "EXPLAINED"  # reviewer accepted a legitimate explanation
    CONFIRMED = "CONFIRMED"  # reviewer confirmed the problem (escalation is Gate 6 case management)


class CaptureAttachment(UuidPk, Base):
    __tablename__ = "capture_attachment"
    __table_args__ = (Index("ix_attachment_tenant_hash", "tenant_id", "sha256"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(300), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)  # METER_PHOTO | SIGNATURE | RECEIPT
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MeterCapture(UuidPk, SyncRevisioned, Base):
    """`id` is the device-generated UUID, so offline retries can never create a second reading."""

    __tablename__ = "meter_capture"
    __table_args__ = (
        Index("ix_meter_capture_machine_time", "machine_id", "captured_at"),
        Index(
            "uq_meter_capture_job_kind_active",
            "job_id",
            "kind",
            unique=True,
            postgresql_where=text("state IN ('ACCEPTED', 'PROVISIONAL') AND kind <> 'DAILY'"),
        ),
        CheckConstraint("kind = 'DAILY' OR job_id IS NOT NULL", name="ck_meter_capture_job_reading"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"), index=True)  # null: DAILY outside a job
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False)
    kind: Mapped[ReadingKind] = mapped_column(_enum(ReadingKind), nullable=False)
    capture_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # AUTOMATIC | MANUAL
    reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    ocr_raw_text: Mapped[str | None] = mapped_column(Text)
    ocr_value: Mapped[Decimal | None] = mapped_column(READING)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_engine: Mapped[str | None] = mapped_column(String(64))  # e.g. "mlkit-text-v2@android", "vision@ios"
    manually_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    photo_attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("capture_attachment.id"))
    photo_sha256: Mapped[str | None] = mapped_column(String(64))
    gps_status: Mapped[GpsStatus] = mapped_column(_enum(GpsStatus), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    location_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location_provider: Mapped[str | None] = mapped_column(String(32))
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # device clock
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # server clock
    supervisor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[CaptureState] = mapped_column(_enum(CaptureState), nullable=False)
    tracker_comparison: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class MeterResetEvent(UuidPk, SyncRevisioned, Base):
    """Documented meter replacement/rollover; must be approved before a lower reading is accepted."""

    __tablename__ = "meter_reset_event"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    old_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    new_reading: Mapped[Decimal] = mapped_column(READING, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("capture_attachment.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # PENDING | APPROVED | REJECTED
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class JobException(UuidPk, SyncRevisioned, Base):
    """Auditable exception — evidence for human review, never an automatic fraud verdict."""

    __tablename__ = "job_exception"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_job_exception_dedupe"),
        Index("ix_job_exception_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False)
    meter_capture_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meter_capture.id"), index=True)
    exception_type: Mapped[ExceptionType] = mapped_column(_enum(ExceptionType, 32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # INFO | WARNING | CRITICAL
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)  # must be reviewed before billing
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[ExceptionStatus] = mapped_column(_enum(ExceptionStatus), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
