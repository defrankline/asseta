"""Data protection records (DEC-032 Phase 5): a tenant's data export jobs and its balance verification runs."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, text
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
