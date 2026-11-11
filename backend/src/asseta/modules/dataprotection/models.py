"""Data protection records (DEC-032 Phase 5): a tenant's data export jobs, its balance verification runs and the
company closure (deletion) requests."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow


class ExportFormat(StrEnum):
    CSV = "CSV"
    JSON = "JSON"


class ExportStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"  # the retention period passed and the file was deleted


class VerificationTrigger(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    PLATFORM = "PLATFORM"


class VerificationOutcome(StrEnum):
    MATCHED = "MATCHED"
    MISMATCHES = "MISMATCHES"


def _enum(e: type[StrEnum], length: int = 16) -> Enum:
    return Enum(e, native_enum=False, length=length, create_constraint=False)


class TenantDataExport(UuidPk, Base):
    """One requested export of a tenant's data: queued by a permission holder, built by the export worker, downloaded
    through a short-lived link and deleted when the tenant's retention period passes. At most one is active."""

    __tablename__ = "tenant_data_export"
    __table_args__ = (
        Index(
            "uq_tenant_data_export_active",
            "tenant_id",
            unique=True,
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
        Index("ix_tenant_data_export_status", "status", "requested_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    format: Mapped[ExportFormat] = mapped_column(_enum(ExportFormat, 8), nullable=False)
    status: Mapped[ExportStatus] = mapped_column(_enum(ExportStatus), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    object_key: Mapped[str | None] = mapped_column(String(300))
    sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    table_count: Mapped[int | None] = mapped_column(Integer)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    evidence_count: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BalanceVerificationRun(UuidPk, Base):
    """One verification of a tenant's balances against its underlying records. Written once, when finished
    (append-only: trigger + no UPDATE/DELETE grant). It only reports: the ledger prevails, nothing is corrected."""

    __tablename__ = "balance_verification_run"
    __table_args__ = (Index("ix_balance_verification_tenant_time", "tenant_id", "started_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    trigger: Mapped[VerificationTrigger] = mapped_column(_enum(VerificationTrigger), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[VerificationOutcome] = mapped_column(_enum(VerificationOutcome), nullable=False)
    checked_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)  # {check, checked, mismatches}
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)  # capped; see `findings_truncated`
    findings_truncated: Mapped[bool] = mapped_column(nullable=False, default=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)


class DeletionStatus(StrEnum):
    REQUESTED = "REQUESTED"  # waiting period running: the company is read-only
    CANCELLED = "CANCELLED"  # cancelled before it started: normal access restored
    IN_PROGRESS = "IN_PROGRESS"  # the deletion started; it resumes from `steps` until it completes
    COMPLETED = "COMPLETED"  # every record of the company deleted; only the closure record and billing remain


ACTIVE_DELETION_STATUSES = (DeletionStatus.REQUESTED, DeletionStatus.IN_PROGRESS)


class CompanyDeletionRequest(UuidPk, Base):
    """A company owner's request to close the company and delete all its data. The company is read-only from the
    request until `scheduled_for` (the platform-wide waiting period), when the data protection worker deletes everything
    but the platform operator's billing records about the company and this row. Each finished step is recorded in
    `steps`, so a deletion that fails halfway resumes where it stopped. At most one active request per company."""

    __tablename__ = "company_deletion_request"
    __table_args__ = (
        Index(
            "uq_company_deletion_request_active",
            "tenant_id",
            unique=True,
            postgresql_where=text("status IN ('REQUESTED', 'IN_PROGRESS')"),
        ),
        Index("ix_company_deletion_request_due", "status", "scheduled_for"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    status: Mapped[DeletionStatus] = mapped_column(_enum(DeletionStatus), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    waiting_days: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    # Platform "execute now" (the owner asked in writing): who, when and why; the worker then runs it at once.
    execute_now_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    execute_now_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execute_now_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    # step name -> what it did ({"at": ..., counts}); `tables` lists the tables already emptied (resume point).
    steps: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
