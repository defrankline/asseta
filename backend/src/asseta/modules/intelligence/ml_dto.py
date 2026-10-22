"""ML governance DTOs (class names are unique across the API for OpenAPI). Tenant-facing DTOs carry readiness and
deployment facts in plain terms only — never a score."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.intelligence.ml_models import ModelAction, ModelAlgorithm, ModelStatus, ReadinessState

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


class MlModelVersionDetailDto(BaseModel):
    model: MlModelVersionDto
    evaluation: MlEvaluationDto | None
    approvals: list[MlApprovalDto]
    manifest: MlManifestSummaryDto
    drift: dict[str, Any] | None = Field(
        default=None, description="Feature drift (PSI per feature) is recorded once inference runs (Gate 6D)"
    )


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


class TenantMlStatusDto(BaseModel):
    model_name: str
    readiness: MlReadinessDto | None
    deployed: TenantMlDeploymentDto | None
    inference_enabled: bool
    summary: str = Field(description="Plain-language status for the tenant")
