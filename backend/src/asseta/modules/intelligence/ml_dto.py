"""ML governance DTOs (class names are unique across the API for OpenAPI). Tenant-facing DTOs carry readiness and
deployment facts in plain terms only — never a score."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.intelligence.ml_models import ModelAction, ModelAlgorithm, ModelStatus, ReadinessState
from asseta.modules.intelligence.ml_monitoring_models import DecisionState, DriftSummaryLevel, InferenceOutcome

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class _Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MlModelVersionDto(_Dto):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str | None = None
    name: str
    version: int
    algorithm: ModelAlgorithm
    baseline_algorithm: ModelAlgorithm
    feature_set_hash: str
    training_window_start: datetime | None
    training_window_end: datetime | None
    mlflow_run_id: str | None
    tracking_note: str | None
    artifact_sha256: str
    status: ModelStatus
    status_changed_at: datetime
    deployed_at: datetime | None
    evaluation_passed: bool | None = None
    created_at: datetime
    lock_version: int


class MlEvaluationDto(_Dto):
    id: uuid.UUID
    model_version_id: uuid.UUID
    metrics: dict[str, Any] = Field(description="candidate vs baseline metrics (recall@k, alert rate, stability)")
    readiness: dict[str, Any]
    criteria: dict[str, Any]
    passed: bool
    reasons: list[str]
    evaluated_at: datetime


class MlApprovalDto(_Dto):
    id: uuid.UUID
    model_version_id: uuid.UUID
    action: ModelAction
    from_status: ModelStatus | None
    to_status: ModelStatus
    related_model_version_id: uuid.UUID | None
    reason: str
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime


class MlManifestSummaryDto(BaseModel):
    rows: dict[str, int] = Field(description="rows per split (train / validation / test)")
    entities: int
    feature_codes: list[str]
    train_end: str | None
    validation_end: str | None
    purged_rows: int | None
    content_hash: str | None


class MlDriftFeatureDto(BaseModel):
    feature: str
    psi: float | None
    level: str = Field(description="STABLE (< 0.1) | WATCH (0.1-0.25) | DRIFT (>= 0.25) | INSUFFICIENT_DATA")
    n_expected: int
    n_actual: int


class MlDriftDto(_Dto):
    id: uuid.UUID
    model_version_id: uuid.UUID
    computed_at: datetime
    train_start: datetime | None
    train_end: datetime | None
    recent_start: datetime | None
    recent_end: datetime | None
    n_train: int
    n_recent: int
    features: list[MlDriftFeatureDto]
    level: DriftSummaryLevel
    summary: str


class MlMonitoringDto(BaseModel):
    latency_p50_ms: float | None = Field(description="Median inference latency over recent OK runs")
    latency_p95_ms: float | None
    runs_by_outcome: dict[str, int] = Field(description="inference_audit rows per outcome (OK / SKIPPED / ERROR)")
    predictions_by_state: dict[str, int] = Field(description="prediction rows per decision state")
    last_inference_at: datetime | None
    last_error: str | None = Field(description="Reason of the latest run when it failed")


class MlModelVersionDetailDto(BaseModel):
    model: MlModelVersionDto
    evaluation: MlEvaluationDto | None
    approvals: list[MlApprovalDto]
    manifest: MlManifestSummaryDto
    drift: MlDriftDto | None = Field(default=None, description="Latest PSI drift check (training vs recent 4 weeks)")
    monitoring: MlMonitoringDto | None = None


class MlPredictionDto(_Dto):
    """Platform-only view of a prediction with its full provenance."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    model_version_id: uuid.UUID
    model_name: str
    model_version_number: int
    deployment_mode: str
    evaluation_id: uuid.UUID | None
    approval_id: uuid.UUID | None
    subject_type: str
    subject_id: uuid.UUID
    as_of: datetime
    feature_set_hash: str
    feature_snapshot_ids: list[uuid.UUID]
    data_cutoff: datetime | None
    features_present: int
    score: Decimal | None = Field(description="Calibrated percentile vs held-out weeks; null unless calibrated")
    raw_score: float | None = Field(description="Model-specific scale; never a probability")
    calibrated: bool
    baseline_score: Decimal | None
    baseline_raw_score: float | None
    threshold: Decimal
    would_surface: bool
    contributions: list[dict[str, Any]]
    explanations: list[str]
    policy_version: str
    decision_state: DecisionState
    case_id: uuid.UUID | None
    inference_run_id: uuid.UUID
    created_at: datetime


class MlInferenceAuditDto(_Dto):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    model_version_id: uuid.UUID | None
    inference_run_id: uuid.UUID
    started_at: datetime
    latency_ms: int
    input_rows: int
    predictions_written: int
    surfaced: int
    outcome: InferenceOutcome
    reason: str | None


class TenantPredictionDto(BaseModel):
    """A surfaced model observation as a tenant sees it: neutral observations and the case to review, no score."""

    id: uuid.UUID
    machine_id: uuid.UUID
    week_ending: datetime
    model_name: str
    model_version: int
    observations: list[str]
    case_id: uuid.UUID | None
    created_at: datetime


class MlModelActionIn(BaseModel):
    reason: Reason
    lock_version: int | None = Field(default=None, ge=1, description="Optimistic concurrency token from last read")


class MlSettingsDto(BaseModel):
    inference_enabled: bool
    reason: str
    updated_by: uuid.UUID | None
    updated_at: datetime | None
    lock_version: int = Field(description="0 until the switch has been changed for the first time")


class MlSettingsIn(BaseModel):
    inference_enabled: bool
    reason: Reason
    lock_version: int | None = Field(default=None, ge=0)


class MlReadinessDto(_Dto):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str | None = None
    model_name: str
    status: ReadinessState
    reasons: list[str] = Field(description="Each unmet minimum, in plain words")
    observed: dict[str, Any]
    minimums: dict[str, Any]
    snapshot_rows: int
    model_version_id: uuid.UUID | None
    computed_at: datetime


class MlSnapshotRunIn(BaseModel):
    from_date: date
    to_date: date


class MlSnapshotRunDto(BaseModel):
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    week_ends: list[datetime]
    machines: int
    written: int
    skipped_existing: int
    skipped_future: int


class MlTrainingRunDto(BaseModel):
    readiness: MlReadinessDto
    model: MlModelVersionDto | None


class TenantMlDeploymentDto(BaseModel):
    name: str
    version: int
    mode: str = Field(description="SHADOW (observed only, never shown as findings) or ACTIVE")
    deployed_at: datetime | None


TenantMlState = Literal["MODEL_OFF", "NOT_ASSESSED", "NOT_ENOUGH_HISTORY", "EVALUATING", "LEARNING_SHADOW", "ACTIVE"]


class TenantMlStatusDto(BaseModel):
    model_name: str
    state: TenantMlState
    label: str = Field(
        description='"Model off" | "Learning (shadow)" | "Not enough history yet: <reasons>" | "Active" | ...'
    )
    readiness: MlReadinessDto | None
    deployed: TenantMlDeploymentDto | None
    inference_enabled: bool
    summary: str = Field(description="Plain-language status for the tenant")
