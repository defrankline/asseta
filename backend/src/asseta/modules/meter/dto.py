import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asseta.modules.meter.models import CaptureState, ExceptionStatus, ExceptionType, GpsStatus, ReadingKind
from asseta.modules.policy.schemas import CaptureMode

Reading = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GpsIn(BaseModel):
    """Result of the mandatory GPS attempt; never fabricate coordinates on failure."""

    status: GpsStatus
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    captured_at: datetime | None = None
    provider: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _consistent(self) -> "GpsIn":
        has_coords = self.latitude is not None and self.longitude is not None
        if (self.status is GpsStatus.FIX) != has_coords:
            raise ValueError("coordinates must be present exactly when status is FIX")
        if self.status is GpsStatus.FIX and self.captured_at is None:
            raise ValueError("FIX requires captured_at")
        return self


class MeterCaptureIn(BaseModel):
    id: uuid.UUID = Field(description="Device-generated UUID (idempotency key for offline sync)")
    job_id: uuid.UUID | None = Field(default=None, description="Required for OPENING/CLOSING; optional for DAILY")
    machine_id: uuid.UUID | None = Field(
        default=None, description="DAILY reading outside a job: the machine read (must match the job's when both)"
    )
    kind: ReadingKind
    capture_mode: CaptureMode
    reading: Reading
    ocr_raw_text: str | None = Field(default=None, max_length=500)
    ocr_value: Reading | None = None
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_engine: str | None = Field(default=None, max_length=64)
    photo_attachment_id: uuid.UUID | None = None
    gps: GpsIn
    device_id: str = Field(min_length=3, max_length=128)
    captured_at: datetime
    policy_version_ids: list[uuid.UUID] = Field(
        default_factory=list, description="METER_CAPTURE snapshot the device enforced offline"
    )
    supersedes_id: uuid.UUID | None = Field(default=None, description="Approved correction of a prior capture")

    @model_validator(mode="after")
    def _target(self) -> "MeterCaptureIn":
        if self.kind is not ReadingKind.DAILY and self.job_id is None:
            raise ValueError("job_id is required for OPENING and CLOSING readings")
        if self.job_id is None and self.machine_id is None:
            raise ValueError("a DAILY reading names its machine (machine_id) or its job (job_id)")
        return self


class FindingDto(BaseModel):
    type: ExceptionType
    severity: str
    blocking: bool
    evidence: dict[str, Any]


class MeterCaptureDto(Dto):
    id: uuid.UUID
    job_id: uuid.UUID | None
    machine_id: uuid.UUID
    kind: ReadingKind
    capture_mode: str
    reading: Decimal
    ocr_value: Decimal | None
    ocr_confidence: float | None
    manually_corrected: bool
    photo_attachment_id: uuid.UUID | None
    photo_sha256: str | None
    gps_status: GpsStatus
    latitude: float | None
    longitude: float | None
    accuracy_m: float | None
    location_captured_at: datetime | None
    captured_at: datetime
    received_at: datetime
    policy_version: str
    state: CaptureState
    tracker_comparison: dict[str, Any] | None
    supersedes_id: uuid.UUID | None


class CaptureResultDto(BaseModel):
    capture: MeterCaptureDto
    findings: list[FindingDto]


class AttachmentDto(Dto):
    id: uuid.UUID
    sha256: str
    content_type: str
    size_bytes: int
    purpose: str
    uploaded_at: datetime


class ResetIn(BaseModel):
    machine_id: uuid.UUID
    old_reading: Reading
    new_reading: Reading
    effective_at: datetime
    reason: str = Field(min_length=10, max_length=2000)
    evidence_attachment_id: uuid.UUID | None = None


class ResetDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    old_reading: Decimal
    new_reading: Decimal
    effective_at: datetime
    reason: str
    evidence_attachment_id: uuid.UUID | None
    status: str
    requested_by: uuid.UUID | None
    decided_at: datetime | None


class ExceptionDto(Dto):
    id: uuid.UUID
    job_id: uuid.UUID | None
    machine_id: uuid.UUID
    meter_capture_id: uuid.UUID | None
    exception_type: ExceptionType
    severity: str
    blocking: bool
    evidence: dict[str, Any]
    policy_version: str | None
    status: ExceptionStatus
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime


class ReviewIn(BaseModel):
    outcome: Literal["EXPLAINED", "CONFIRMED"]
    note: str = Field(min_length=5, max_length=2000)
