"""DTOs for the work allocation ledger (DEC-032 A1) and the daily operational report (A4)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.meter.allocation_models import (
    AllocationKind,
    AllocationSource,
    AllocationStatus,
    DailyReportStatus,
)

Hours = Annotated[Decimal, Field(gt=0, le=Decimal("100000"), max_digits=14, decimal_places=2)]
NonNegHours = Annotated[Decimal, Field(ge=0, le=Decimal("100000"), max_digits=14, decimal_places=2)]
Note = Annotated[str, StringConstraints(min_length=5, max_length=2000, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AllocationLotDto(BaseModel):
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    hours: Decimal


class WorkAllocationDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    work_date: date
    start_ref: uuid.UUID
    start_reading: Decimal
    start_at: datetime
    end_ref: uuid.UUID
    end_reading: Decimal
    end_at: datetime
    meter_epoch: int
    hours: Decimal
    kind: AllocationKind
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    job_id: uuid.UUID | None
    job_number: str | None = None
    activity_type: str | None
    reason_id: uuid.UUID | None
    reason_name: str | None = None
    classification_id: uuid.UUID | None
    changeover_id: uuid.UUID | None
    reading_review: str
    lots: list[AllocationLotDto]
    evidence_attachment_ids: list[uuid.UUID]
    source: AllocationSource
    status: AllocationStatus
    supersedes_id: uuid.UUID | None
    superseded_by_ids: list[uuid.UUID] = Field(default_factory=list)
    correction_group_id: uuid.UUID | None
    correction_reason: str | None
    recorded_by: uuid.UUID | None
    recorded_by_name: str | None = None
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    superseded_at: datetime | None
    policy_version: str
    created_at: datetime


class AllocationPartIn(BaseModel):
    """One part of a correction. Parts are taken from the entry's meter range in the order given."""

    hours: Hours
    kind: AllocationKind
    customer_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    reason_id: uuid.UUID | None = Field(default=None, description="AUTHORIZED_ACTIVITY: tenant category or variance")


class AllocationCorrectionIn(BaseModel):
    parts: list[AllocationPartIn] = Field(min_length=1, max_length=10)
    reason: Note
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class AllocationCorrectionDto(BaseModel):
    group_id: uuid.UUID
    status: AllocationStatus = Field(description="PROPOSED, ACTIVE (applied) or REJECTED")
    supersedes_id: uuid.UUID | None
    entries: list[WorkAllocationDto]


class AllocationDayDto(BaseModel):
    """Per machine and tenant-local day: total engine hours = customer + authorized + unexplained, with the difference
    shown (hours not yet allocated, for example a reading that went down with no approved reset)."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    day: date
    total_engine_hours: Decimal
    customer_hours: Decimal
    authorized_hours: Decimal
    unexplained_hours: Decimal
    allocated_hours: Decimal
    difference_hours: Decimal
    reconciled: bool


# --- daily operational report ------------------------------------------------------------------------------------
class UnbillableLineIn(BaseModel):
    reason_id: uuid.UUID = Field(description="Tenant list entry of kind UNBILLABLE_REASON")
    hours: Hours


class UnbillableLineDto(BaseModel):
    reason_id: uuid.UUID
    reason_name: str | None = None
    hours: Decimal


class DailyReportIn(BaseModel):
    id: uuid.UUID = Field(description="Device-generated id (offline idempotency)")
    machine_id: uuid.UUID
    report_date: date
    opening_ref: uuid.UUID = Field(description="The day's opening reading (a meter capture)")
    closing_ref: uuid.UUID = Field(description="The day's closing reading (a meter capture)")
    billable_hours: NonNegHours | None = Field(default=None, description="Default: total minus unbillable hours")
    unbillable: list[UnbillableLineIn] = Field(default_factory=list, max_length=20)
    note: str | None = Field(default=None, max_length=2000)
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    supersedes_id: uuid.UUID | None = Field(default=None, description="The report this one replaces (e.g. returned)")
    client_created_at: datetime


class ReportAllocationDto(BaseModel):
    allocation_id: uuid.UUID
    kind: AllocationKind
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    job_id: uuid.UUID | None
    job_number: str | None = None
    activity_type: str | None
    start_reading: Decimal
    end_reading: Decimal
    hours: Decimal


class DailyReportDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    report_date: date
    opening_ref: uuid.UUID
    opening_reading: Decimal
    closing_ref: uuid.UUID
    closing_reading: Decimal
    total_hours: Decimal
    billable_hours: Decimal
    unbillable_hours: Decimal
    difference_hours: Decimal
    unbillable: list[UnbillableLineDto]
    allocations: list[ReportAllocationDto]
    evidence_attachment_ids: list[uuid.UUID]
    note: str | None
    status: DailyReportStatus
    supersedes_id: uuid.UUID | None
    duplicate_of_id: uuid.UUID | None
    is_duplicate: bool = False
    is_late: bool
    submitted_by: uuid.UUID | None
    submitted_by_name: str | None = None
    submitted_at: datetime
    client_created_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None
    review_note: str | None
    source: str
    policy_version: str


class DailyReportPrefillDto(BaseModel):
    """What the day's readings and allocations already say, to fill the report form."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    report_date: date
    opening_ref: uuid.UUID | None
    opening_reading: Decimal | None
    opening_at: datetime | None
    closing_ref: uuid.UUID | None
    closing_reading: Decimal | None
    closing_at: datetime | None
    total_hours: Decimal | None
    customer_hours: Decimal
    authorized_hours: Decimal
    unexplained_hours: Decimal
    allocations: list[ReportAllocationDto]
    existing_report_ids: list[uuid.UUID] = Field(description="Active reports already submitted for this machine-day")


class DailyReportReviewIn(BaseModel):
    decision: Literal["REVIEWED", "RETURNED"]
    note: Note
