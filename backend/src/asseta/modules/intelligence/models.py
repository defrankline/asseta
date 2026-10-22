"""Deterministic risk signals and investigation cases (ADR-007, prompt.md §7).

Four kinds of record stay separate: observed facts (domain rows), deterministic signals (`risk_signal`, plus the
existing meter exceptions / tracking alerts / segregation-of-duties events), model predictions (later) and human
decisions (`case_outcome`). Nothing here means "fraud = true": a case collects evidence for a person to review,
and only a reviewer records an outcome. Signals, links, notes and outcomes are append-only (DB guards)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


def _uuids() -> ARRAY[uuid.UUID]:
    return ARRAY(UUID(as_uuid=True))


class SignalSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


SEVERITY_RANK = {SignalSeverity.INFO: 0, SignalSeverity.WARNING: 1, SignalSeverity.CRITICAL: 2}


class RuleCode(StrEnum):
    UNREPORTED_ENGINE_ACTIVITY = "UNREPORTED_ENGINE_ACTIVITY"
    DUPLICATE_RECEIPT = "DUPLICATE_RECEIPT"
    FUEL_ALLOWANCE_EXCEEDED = "FUEL_ALLOWANCE_EXCEEDED"
    EXPENSE_THRESHOLD_EXCEEDED = "EXPENSE_THRESHOLD_EXCEEDED"
    CASH_NOT_HANDED_OVER = "CASH_NOT_HANDED_OVER"
    WORK_WITHOUT_AUTHORIZATION = "WORK_WITHOUT_AUTHORIZATION"


class SubjectType(StrEnum):
    MACHINE = "MACHINE"
    JOB = "JOB"
    STAFF = "STAFF"
    EXPENSE = "EXPENSE"
    USER = "USER"  # a login without a staff record (e.g. a segregation-of-duties attempt by office staff)


class SignalStatus(StrEnum):
    OPEN = "OPEN"  # stored, not yet attached to a case
    LINKED = "LINKED"  # attached to an investigation case
    DISMISSED = "DISMISSED"


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"  # assigned or being worked on (first note)
    RESOLVED = "RESOLVED"  # an outcome was recorded; reopening returns to IN_REVIEW


class CaseSourceType(StrEnum):
    RISK_SIGNAL = "RISK_SIGNAL"
    METER_EXCEPTION = "METER_EXCEPTION"
    TRACKING_ALERT = "TRACKING_ALERT"
    SOD_EVENT = "SOD_EVENT"
    PREDICTION = "PREDICTION"  # surfaced model predictions only (never shadow ones)


class CaseOutcomeKind(StrEnum):
    CONFIRMED_ISSUE = "CONFIRMED_ISSUE"
    UNCONFIRMED = "UNCONFIRMED"
    LEGITIMATE_EXPLANATION = "LEGITIMATE_EXPLANATION"


class CaseNoteKind(StrEnum):
    NOTE = "NOTE"
    REOPEN = "REOPEN"  # the reason a resolved case was reopened


class RiskSignal(UuidPk, Base):
    """Explainable rule output: facts + thresholds (evidence), never a conclusion. Only `status` may change."""

    __tablename__ = "risk_signal"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_risk_signal_dedupe"),
        Index("ix_risk_signal_tenant_time", "tenant_id", "created_at"),
        Index("ix_risk_signal_subject", "tenant_id", "subject_type", "subject_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    rule_code: Mapped[RuleCode] = mapped_column(_enum(RuleCode, 48), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[SignalSeverity] = mapped_column(_enum(SignalSeverity, 16), nullable=False)
    subject_type: Mapped[SubjectType] = mapped_column(_enum(SubjectType, 16), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"))
    staff_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    # People whose own records produced the evidence (segregation of duties on the resulting case).
    involved_user_ids: Mapped[list[uuid.UUID]] = mapped_column(_uuids(), nullable=False, default=list)
    involved_staff_ids: Mapped[list[uuid.UUID]] = mapped_column(_uuids(), nullable=False, default=list)
    status: Mapped[SignalStatus] = mapped_column(_enum(SignalStatus, 16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AnomalyCase(UuidPk, Base):
    """Investigation case `CASE-YYYY-NNNNN`. Subject and opening facts are frozen (guard trigger); status, severity
    (only upwards), assignee and resolution stamps change through audited service calls."""

    __tablename__ = "anomaly_case"
    __table_args__ = (
        UniqueConstraint("tenant_id", "case_number", name="uq_anomaly_case_number"),
        Index("ix_anomaly_case_subject", "tenant_id", "subject_type", "subject_id", "status"),
        Index("ix_anomaly_case_status", "tenant_id", "status", "last_signal_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    case_number: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_type: Mapped[SubjectType] = mapped_column(_enum(SubjectType, 16), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"))
    staff_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"))
    severity: Mapped[SignalSeverity] = mapped_column(_enum(SignalSeverity, 16), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(_enum(CaseStatus, 16), nullable=False)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_signal_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class AnomalyCaseCounter(Base):
    """Per-tenant, per-year gap-free case counter (row lock via INSERT .. ON CONFLICT DO UPDATE)."""

    __tablename__ = "anomaly_case_counter"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False)


class CaseSignal(UuidPk, Base):
    """Link from a case to one signal of any source, with an evidence snapshot taken when linked. A source belongs
    to at most one case (unique), so re-running detectors or redelivering events never links twice."""

    __tablename__ = "case_signal"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_type", "source_id", name="uq_case_signal_source"),
        Index("ix_case_signal_case", "case_id", "observed_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anomaly_case.id"), nullable=False)
    source_type: Mapped[CaseSourceType] = mapped_column(_enum(CaseSourceType, 24), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)  # rule code / exception type / alert type
    severity: Mapped[SignalSeverity] = mapped_column(_enum(SignalSeverity, 16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    involved_user_ids: Mapped[list[uuid.UUID]] = mapped_column(_uuids(), nullable=False, default=list)
    involved_staff_ids: Mapped[list[uuid.UUID]] = mapped_column(_uuids(), nullable=False, default=list)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CaseNote(UuidPk, Base):
    __tablename__ = "case_note"
    __table_args__ = (
        Index("ix_case_note_case", "case_id", "created_at"),
        CheckConstraint("char_length(body) >= 1", name="ck_case_note_body"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anomaly_case.id"), nullable=False)
    kind: Mapped[CaseNoteKind] = mapped_column(_enum(CaseNoteKind, 16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CaseOutcome(UuidPk, Base):
    """The human decision for one resolution of a case. Immutable; a reopened case gets a new outcome."""

    __tablename__ = "case_outcome"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence", name="uq_case_outcome_sequence"),
        CheckConstraint("char_length(explanation) >= 10", name="ck_case_outcome_explanation"),
        Index("ix_case_outcome_tenant", "tenant_id", "decided_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anomaly_case.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[CaseOutcomeKind] = mapped_column(_enum(CaseOutcomeKind, 32), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


ACTIVE_CASE_STATUSES = (CaseStatus.OPEN, CaseStatus.IN_REVIEW)
