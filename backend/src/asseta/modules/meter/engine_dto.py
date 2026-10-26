"""Engine-hour accountability DTOs: baselines, tenant explanation lists, ledger reconciliation, classifications and
reading corrections."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.meter.dto import GpsIn, MeterCaptureIn, Reading
from asseta.modules.meter.engine_models import (
    BaselineSource,
    ClassificationOutcome,
    EngineHourReasonKind,
    MeterProposalStatus,
)
from asseta.modules.meter.ledger import ReadingReview, SegmentClassification, SegmentKind

Code = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
Note = Annotated[str, StringConstraints(min_length=5, max_length=2000, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeterDecisionIn(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    note: Note


# --- baselines ---------------------------------------------------------------------------------------------------
class BaselineIn(BaseModel):
    """A reading taken to establish the machine's initial engine hours (evidence as for any reading)."""

    id: uuid.UUID | None = Field(default=None, description="Device-generated id (offline idempotency)")
    machine_id: uuid.UUID
    reading: Reading
    captured_at: datetime
    photo_attachment_id: uuid.UUID | None = None
    gps: GpsIn | None = None
    device_id: str | None = Field(default=None, min_length=3, max_length=128)
    note: str | None = Field(default=None, max_length=2000)


class BaselineFromReadingIn(BaseModel):
    machine_id: uuid.UUID
    capture_id: uuid.UUID | None = Field(
        default=None, description="Reading to propose as the baseline; default: the machine's earliest live reading"
    )
    note: str | None = Field(default=None, max_length=2000)


class BaselineDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    reading: Decimal
    captured_at: datetime
    source: BaselineSource
    source_capture_id: uuid.UUID | None
    photo_attachment_id: uuid.UUID | None
    latitude: float | None
    longitude: float | None
    accuracy_m: float | None
    note: str | None
    status: MeterProposalStatus
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None


# --- tenant lists ----------------------------------------------------------------------------------------------
class EngineHourReasonIn(BaseModel):
    kind: EngineHourReasonKind
    code: Code
    name: Name
    description: str | None = Field(default=None, max_length=1000)


class EngineHourReasonUpdateIn(BaseModel):
    code: Code
    name: Name
    description: str | None = Field(default=None, max_length=1000)
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class EngineHourReasonDto(Dto):
    id: uuid.UUID
    kind: EngineHourReasonKind
    code: str
    name: str
    description: str | None
    is_active: bool
    version: int
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


# --- ledger ------------------------------------------------------------------------------------------------------
class ReconciliationStatus(StrEnum):
    NO_BASELINE = "NO_BASELINE"  # reconciliation has not begun: no approved baseline yet
    RECONCILED = "RECONCILED"  # every engine hour is allocated or explained
    PENDING_REVIEW = "PENDING_REVIEW"  # only readings awaiting review / explanations awaiting approval remain
    UNEXPLAINED = "UNEXPLAINED"  # some verified engine hours are not yet explained


class LedgerPointDto(BaseModel):
    ref: uuid.UUID
    source: str = Field(description="BASELINE or the reading kind (OPENING / CLOSING / DAILY)")
    at: datetime
    reading: Decimal
    job_id: uuid.UUID | None


class ClassificationRefDto(BaseModel):
    id: uuid.UUID
    status: MeterProposalStatus
    outcome: ClassificationOutcome
    reason_id: uuid.UUID


class SegmentDto(BaseModel):
    kind: SegmentKind
    hours: Decimal
    classification: SegmentClassification
    job_id: uuid.UUID | None
    job_number: str | None
    approved: ClassificationRefDto | None
    proposal: ClassificationRefDto | None
    activity_type: str | None = Field(
        default=None, description="NON_REVENUE segments: the work-log type (e.g. MOBILIZATION) — DEC-031 R1"
    )


class IntervalDto(BaseModel):
    machine_id: uuid.UUID
    start: LedgerPointDto
    end: LedgerPointDto
    hours: Decimal
    raw_hours: Decimal
    reset_applied: bool
    inconsistent: bool
    review: ReadingReview
    opened_at: datetime
    age_days: int
    overlapping_job_ids: list[uuid.UUID]
    segments: list[SegmentDto]


class TotalsDto(BaseModel):
    total_hours: Decimal
    customer_work_hours: Decimal
    non_revenue_hours: Decimal = Field(
        default=Decimal(0),
        description="Non-revenue work-log time inside job windows (revenue-hour basis on; else 0) — DEC-031 R1",
    )
    unallocated_hours: Decimal
    approved_non_customer_hours: Decimal
    identified_variance_hours: Decimal
    unexplained_hours: Decimal
    proposed_hours: Decimal
    pending_review_hours: Decimal


class JobOverlapDto(BaseModel):
    first_job_id: uuid.UUID
    second_job_id: uuid.UUID
    basis: str


class MachineEngineHoursDto(BaseModel):
    machine_id: uuid.UUID
    machine_code: str
    machine_name: str
    status: ReconciliationStatus
    baseline: BaselineDto | None
    baseline_proposal: BaselineDto | None
    policy_version: str
    totals: TotalsDto
    intervals: list[IntervalDto]
    overlaps: list[JobOverlapDto]


class MachineEngineHoursSummaryDto(BaseModel):
    machine_id: uuid.UUID
    machine_code: str
    machine_name: str
    status: ReconciliationStatus
    baseline_reading: Decimal | None
    baseline_pending: bool
    last_reading: Decimal | None
    last_reading_at: datetime | None
    open_items: int
    oldest_open_item_days: int | None
    totals: TotalsDto


class UnallocatedSegmentDto(BaseModel):
    machine_id: uuid.UUID
    machine_code: str
    machine_name: str
    start: LedgerPointDto
    end: LedgerPointDto
    hours: Decimal
    review: ReadingReview
    classification: SegmentClassification
    opened_at: datetime
    age_days: int
    investigation_due: bool = Field(description="Older than the policy ageing threshold (an investigation opens)")
    approved: ClassificationRefDto | None
    proposal: ClassificationRefDto | None


# --- classifications ---------------------------------------------------------------------------------------------
class ClassificationIn(BaseModel):
    machine_id: uuid.UUID
    start_ref: uuid.UUID = Field(description="The segment's start point (`start.ref` in the ledger)")
    end_ref: uuid.UUID = Field(description="The segment's end point (`end.ref` in the ledger)")
    outcome: ClassificationOutcome
    reason_id: uuid.UUID = Field(description="Tenant list entry: a category (non-customer) or a variance reason")
    note: Note


class ClassificationDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    start_ref: uuid.UUID
    end_ref: uuid.UUID
    start_at: datetime
    end_at: datetime
    hours: Decimal
    outcome: ClassificationOutcome
    reason_id: uuid.UUID
    reason_name: str | None = None
    note: str
    status: MeterProposalStatus
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    policy_version: str


# --- corrections -------------------------------------------------------------------------------------------------
class CorrectionIn(BaseModel):
    superseded_capture_id: uuid.UUID
    reason: Annotated[str, StringConstraints(min_length=10, max_length=2000, strip_whitespace=True)]
    replacement: MeterCaptureIn = Field(description="The corrected reading with its own evidence (same kind/job)")


class CorrectionDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    job_id: uuid.UUID | None
    job_number: str | None = None
    superseded_capture_id: uuid.UUID
    replacement_capture_id: uuid.UUID
    old_reading: Decimal
    new_reading: Decimal
    reason: str
    status: MeterProposalStatus
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    policy_version: str
