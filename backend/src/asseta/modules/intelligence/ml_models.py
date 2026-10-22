"""ML data foundation and model governance records (ADR-007 "ML data foundation" / "Model lifecycle").

* `feature_definition` — platform reference data mirrored from the `asseta.ml.features` registry; immutable per
  (code, version). Tenants may read it; only platform/system scopes insert.
* `feature_snapshot` — one point-in-time feature value per (tenant, entity, feature@version, as_of); append-only.
* `model_version` / `model_evaluation` / `model_approval` — the governance record. MLflow keeps runs and artifacts,
  but what may run, and why, lives here: evaluations and approvals are immutable, every lifecycle action is an
  approval row with a reason, and `model_version.status` only moves along the guarded transition graph (DB trigger).
* `ml_setting` — the platform-wide inference hard switch (single row).
* `model_readiness` — append-only history of data-sufficiency assessments so the UI can say *why* there is no model.

There is no score, label or verdict about a person anywhere in these tables.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


ANOMALY_MODEL_NAME = "machine-week-anomaly"
SOURCE_OBSERVED = "observed"  # computed from the tenant's own domain facts
SOURCE_SYNTHETIC = "synthetic"  # `asseta-ml demo` only (development); never used by real training or insights
SNAPSHOT_SOURCES = (SOURCE_OBSERVED, SOURCE_SYNTHETIC)


class FeatureEntityType(StrEnum):
    MACHINE = "MACHINE"
    JOB = "JOB"
    STAFF = "STAFF"


class ModelAlgorithm(StrEnum):
    ISOLATION_FOREST = "ISOLATION_FOREST"
    ROBUST_Z_BASELINE = "ROBUST_Z_BASELINE"


class ModelStatus(StrEnum):
    TRAINED = "TRAINED"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    DEPLOYED_SHADOW = "DEPLOYED_SHADOW"
    DEPLOYED_ACTIVE = "DEPLOYED_ACTIVE"
    RETIRED = "RETIRED"
    DISABLED = "DISABLED"
    REJECTED = "REJECTED"


DEPLOYED_STATUSES = (ModelStatus.DEPLOYED_SHADOW, ModelStatus.DEPLOYED_ACTIVE)

# The allowed status graph; mirrored by the `guard_model_version` trigger (g6sec0000002). Same-status updates are
# allowed so stamping `deployed_at` / `lock_version` never needs a transition.
MODEL_TRANSITIONS: dict[ModelStatus, frozenset[ModelStatus]] = {
    ModelStatus.TRAINED: frozenset({ModelStatus.EVALUATED, ModelStatus.REJECTED, ModelStatus.DISABLED}),
    ModelStatus.EVALUATED: frozenset(
        {
            ModelStatus.APPROVED,
            ModelStatus.DEPLOYED_SHADOW,
            ModelStatus.REJECTED,
            ModelStatus.RETIRED,
            ModelStatus.DISABLED,
        }
    ),
    ModelStatus.APPROVED: frozenset(
        {
            ModelStatus.DEPLOYED_SHADOW,
            ModelStatus.DEPLOYED_ACTIVE,
            ModelStatus.REJECTED,
            ModelStatus.RETIRED,
            ModelStatus.DISABLED,
        }
    ),
    ModelStatus.DEPLOYED_SHADOW: frozenset({ModelStatus.DEPLOYED_ACTIVE, ModelStatus.RETIRED, ModelStatus.DISABLED}),
    ModelStatus.DEPLOYED_ACTIVE: frozenset({ModelStatus.RETIRED, ModelStatus.DISABLED}),
    # A retired version can come back only through ROLLBACK (to the deployment mode it last had).
    ModelStatus.RETIRED: frozenset({ModelStatus.DEPLOYED_SHADOW, ModelStatus.DEPLOYED_ACTIVE, ModelStatus.DISABLED}),
    ModelStatus.DISABLED: frozenset(),
    ModelStatus.REJECTED: frozenset(),
}


class ModelAction(StrEnum):
    TRAIN = "TRAIN"  # recorded by the training job (no human decision; reason = run summary)
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DEPLOY_SHADOW = "DEPLOY_SHADOW"
    DEPLOY_ACTIVE = "DEPLOY_ACTIVE"
    ROLLBACK = "ROLLBACK"
    DISABLE = "DISABLE"
    RETIRE = "RETIRE"


class ReadinessState(StrEnum):
    READY = "READY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class FeatureDefinitionRecord(UuidPk, Base):
    __tablename__ = "feature_definition"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_feature_definition_code_version"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    entity: Mapped[FeatureEntityType] = mapped_column(_enum(FeatureEntityType, 16), nullable=False)
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    window: Mapped[str] = mapped_column(String(16), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class FeatureSnapshotRecord(UuidPk, Base):
    """`as_of` T only reflects facts whose event time and recording time are <= T (see `intelligence/facts.py`)."""

    __tablename__ = "feature_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "entity_type",
            "entity_id",
            "feature_code",
            "feature_version",
            "as_of",
            name="uq_feature_snapshot_point",
        ),
        Index("ix_feature_snapshot_tenant_asof", "tenant_id", "as_of"),
        CheckConstraint("source IN ('observed', 'synthetic')", name="ck_feature_snapshot_source"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    entity_type: Mapped[FeatureEntityType] = mapped_column(_enum(FeatureEntityType, 16), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    feature_code: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_version: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 9))  # NULL = not computable (honest absence)
    data_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # newest recorded_at used
    n_inputs: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default=SOURCE_OBSERVED)


class ModelVersion(UuidPk, Base):
    """One trained model for one tenant (pooled training is OFF). Only status/deployed stamps ever change."""

    __tablename__ = "model_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_model_version_number"),
        Index(
            "uq_model_version_one_deployed",
            "tenant_id",
            "name",
            unique=True,
            postgresql_where=text("status IN ('DEPLOYED_SHADOW', 'DEPLOYED_ACTIVE')"),
        ),
        Index("ix_model_version_status", "status", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm: Mapped[ModelAlgorithm] = mapped_column(_enum(ModelAlgorithm, 24), nullable=False)
    baseline_algorithm: Mapped[ModelAlgorithm] = mapped_column(_enum(ModelAlgorithm, 24), nullable=False)
    feature_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    training_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64))
    tracking_note: Mapped[str | None] = mapped_column(Text)  # why there is no MLflow run (down / not configured)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_key: Mapped[str] = mapped_column(String(300), nullable=False)
    artifact_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ModelStatus] = mapped_column(_enum(ModelStatus, 24), nullable=False)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": lock_version}  # noqa: RUF012


class ModelEvaluation(UuidPk, Base):
    __tablename__ = "model_evaluation"
    __table_args__ = (UniqueConstraint("model_version_id", name="uq_model_evaluation_model"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_version.id"), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # candidate vs baseline
    readiness: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # promotion + sufficiency criteria
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelApproval(UuidPk, Base):
    """Append-only lifecycle log: every action (human or job) with the status it moved from/to and why."""

    __tablename__ = "model_approval"
    __table_args__ = (
        CheckConstraint("char_length(reason) >= 3", name="ck_model_approval_reason"),
        Index("ix_model_approval_model", "model_version_id", "decided_at"),
        Index("ix_model_approval_tenant_name", "tenant_id", "model_name", "decided_at"),
    )

    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)  # strict order
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_version.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[ModelAction] = mapped_column(_enum(ModelAction, 24), nullable=False)
    from_status: Mapped[ModelStatus | None] = mapped_column(_enum(ModelStatus, 24))
    to_status: Mapped[ModelStatus] = mapped_column(_enum(ModelStatus, 24), nullable=False)
    related_model_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # NULL = system job (CLI/worker)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MlSetting(Base):
    """Platform-wide ML switches (exactly one row, id = 1). `inference_enabled = false` stops all inference."""

    __tablename__ = "ml_setting"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ml_setting_single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    inference_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": lock_version}  # noqa: RUF012


class ModelReadiness(UuidPk, Base):
    """Append-only: one row per training attempt (the latest row is the tenant's current readiness)."""

    __tablename__ = "model_readiness"
    __table_args__ = (Index("ix_model_readiness_latest", "tenant_id", "model_name", "computed_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ReadinessState] = mapped_column(_enum(ReadinessState, 24), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    observed: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    minimums: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_version.id"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
