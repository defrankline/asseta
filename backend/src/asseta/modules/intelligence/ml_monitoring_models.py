"""Model predictions, inference audit and drift records (ADR-007 "Model predictions", Gate 6D).

* `prediction` — one row per (deployed model version, machine, as_of) with full provenance: feature snapshot ids and
  cut-off, model version + evaluation (+ approval when ACTIVE), calibrated score (or NULL with the raw score kept
  separately), neutral contributions/explanations, threshold and policy version, and a `decision_state`.
  `SHADOW` rows are platform-only (RLS); tenants can read their own rows only when `SURFACED`. Append-only.
* `inference_audit` — one row per model per inference attempt (or one SKIPPED row per run when the platform switch is
  off): latency, input rows, outcome OK / SKIPPED / ERROR with the reason. Platform-only, append-only.
* `model_drift` — PSI per feature between the training window and the most recent four weeks of snapshots, with a
  summary level. Platform-only, append-only.

None of these rows is a verdict about a person: a surfaced prediction only adds a "needs review" signal to a case.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
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
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class DecisionState(StrEnum):
    SHADOW = "SHADOW"  # shadow deployment: observed by the platform only, never shown to the tenant
    SURFACED = "SURFACED"  # ACTIVE model, calibrated score at/above threshold: linked to a case for human review
    BELOW_THRESHOLD = "BELOW_THRESHOLD"  # ACTIVE model, scored below the threshold: not shown
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # too few features present, or no calibrated score for an ACTIVE model
    MODEL_DISABLED = "MODEL_DISABLED"  # reserved: inference never runs for a disabled model (nothing is written)


class InferenceOutcome(StrEnum):
    OK = "OK"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class DriftSummaryLevel(StrEnum):
    STABLE = "STABLE"
    WATCH = "WATCH"
    DRIFT = "DRIFT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class Prediction(UuidPk, Base):
    __tablename__ = "prediction"
    __table_args__ = (
        UniqueConstraint("model_version_id", "subject_id", "as_of", name="uq_prediction_point"),
        Index("ix_prediction_tenant_state", "tenant_id", "decision_state", "as_of"),
        Index("ix_prediction_model", "model_version_id", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_version.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    deployment_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # SHADOW | ACTIVE at inference time
    evaluation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_evaluation.id"))
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_approval.id"))  # APPROVE (ACTIVE)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)  # MACHINE (R1)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feature_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_snapshot_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    data_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # newest fact recording time
    features_present: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))  # calibrated percentile; NULL unless calibrated
    raw_score: Mapped[float | None] = mapped_column(Float)  # model-specific scale, never shown as a probability
    calibrated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    baseline_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))  # robust-z baseline, for comparison
    baseline_raw_score: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    would_surface: Mapped[bool] = mapped_column(Boolean, nullable=False)  # calibrated score >= threshold
    contributions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    explanations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    decision_state: Mapped[DecisionState] = mapped_column(_enum(DecisionState, 24), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anomaly_case.id"))  # SURFACED only
    inference_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class InferenceAudit(UuidPk, Base):
    __tablename__ = "inference_audit"
    __table_args__ = (
        Index("ix_inference_audit_model", "model_version_id", "started_at"),
        Index("ix_inference_audit_time", "started_at"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"))  # NULL: platform-wide SKIPPED
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_version.id"))
    inference_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    predictions_written: Mapped[int] = mapped_column(Integer, nullable=False)
    surfaced: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[InferenceOutcome] = mapped_column(_enum(InferenceOutcome, 16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ModelDrift(UuidPk, Base):
    __tablename__ = "model_drift"
    __table_args__ = (Index("ix_model_drift_model", "model_version_id", "computed_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_version.id"), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    train_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    train_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recent_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recent_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    n_train: Mapped[int] = mapped_column(Integer, nullable=False)
    n_recent: Mapped[int] = mapped_column(Integer, nullable=False)
    features: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)  # [{feature, psi, level, n_*}]
    level: Mapped[DriftSummaryLevel] = mapped_column(_enum(DriftSummaryLevel, 24), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
