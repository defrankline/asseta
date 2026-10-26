"""Revenue reconciliation DTOs (DEC-031 R2 daily machine sheet, R3 revenue differences and their reason list)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.revenue.models import RevenueDifferenceStatus

Code = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
Note = Annotated[str, StringConstraints(min_length=5, max_length=2000, strip_whitespace=True)]


class SheetFlag(StrEnum):
    MISSING_DAILY_REPORT = "MISSING_DAILY_REPORT"  # no daily/job reading by the cut-off (engine-hours control)
    UNEXPLAINED_HOURS = "UNEXPLAINED_HOURS"  # verified engine hours outside any job, not yet explained
    ENGINE_ON_WITHOUT_JOB = "ENGINE_ON_WITHOUT_JOB"  # tracker engine-on without a running job (risk signal)
    FUEL_ABOVE_NORM = "FUEL_ABOVE_NORM"  # fuel above the tenant's litres-per-hour allowance (risk signal)
    REVENUE_DIFFERENCE = "REVENUE_DIFFERENCE"  # completed work this day not matched by money beyond tolerance


# --- daily machine sheet ----------------------------------------------------------------------------------------
class SheetMoneyDto(BaseModel):
    currency: str
    expected: Decimal = Field(description="Expected revenue from the day's work (hours x locked rate, + standby/fee)")
    in_progress: Decimal = Field(description="Part of `expected` from jobs still running (not yet billable)")
    attributed: Decimal = Field(description="Invoice lines and prepaid consumption attributed to the day's work")
    difference: Decimal = Field(description="expected - in_progress - attributed (negative: more money than expected)")
    unexplained_hours: Decimal = Field(
        default=Decimal(0), description="Engine hours outside jobs not approved as non-customer activity"
    )
    unexplained_expected: Decimal = Field(
        default=Decimal(0),
        description="Unexplained hours expected as revenue (part of `expected`; 0 when the tenant excludes them)",
    )


class SheetJobDto(BaseModel):
    job_id: uuid.UUID
    job_number: str | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    job_site_id: uuid.UUID | None = None
    job_site_name: str | None = None
    billing_mode: str
    status: str
    customer_work_hours: Decimal
    revenue_hours: Decimal


class DailyMachineSheetRowDto(BaseModel):
    """One machine on one tenant-local day, derived from the engine-hour ledger, jobs, fuel, flags and money."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    day: date
    first_reading: Decimal | None
    last_reading: Decimal | None
    reading_count: int
    engine_hours: Decimal
    customer_work_hours: Decimal = Field(description="Inside job windows, after the revenue-hour basis (R1)")
    non_revenue_hours: Decimal = Field(description="Declared non-revenue work-log time inside jobs (R1; 0 when off)")
    non_revenue_by_type: dict[str, Decimal]
    non_revenue_pending_hours: Decimal = Field(
        default=Decimal(0),
        description="Declared non-revenue work-log time not yet explained and approved: still counted as revenue",
    )
    revenue_hours: Decimal = Field(description="Hours expected to be billed: customer work less non-billable time")
    approved_non_customer_hours: Decimal
    identified_variance_hours: Decimal
    unexplained_hours: Decimal
    pending_review_hours: Decimal
    fuel_litres: Decimal
    jobs: list[SheetJobDto]
    money: list[SheetMoneyDto]
    flags: list[SheetFlag]


class SheetReadingDto(BaseModel):
    id: uuid.UUID
    kind: str
    captured_at: datetime
    reading: Decimal
    state: str
    job_id: uuid.UUID | None
    job_number: str | None = None


class SheetSegmentDto(BaseModel):
    start_ref: uuid.UUID
    end_ref: uuid.UUID
    start_at: datetime
    end_at: datetime
    kind: str
    classification: str
    review: str
    hours_in_day: Decimal
    customer_work_hours_in_day: Decimal
    non_revenue_by_type: dict[str, Decimal]
    job_id: uuid.UUID | None
    job_number: str | None = None


class SheetMoneySourceDto(BaseModel):
    source: Literal["INVOICE_LINE", "PREPAID_CONSUMPTION"]
    ref_id: uuid.UUID = Field(description="Invoice line id or customer-hours ledger entry id")
    parent_id: uuid.UUID = Field(description="Invoice id or customer-hours purchase id")
    job_id: uuid.UUID
    job_number: str | None = None
    currency: str
    amount: Decimal = Field(description="Whole amount of the source (attributed to days pro rata)")
    hours: Decimal | None


class SheetFlagRefDto(BaseModel):
    flag: SheetFlag
    record_type: str = Field(description="job_exception | risk_signal | revenue_difference")
    record_id: uuid.UUID


class SheetFuelDto(BaseModel):
    id: uuid.UUID
    event_type: str
    litres: Decimal
    occurred_at: datetime
    job_id: uuid.UUID | None


class DailyMachineSheetDetailDto(DailyMachineSheetRowDto):
    """The machine-day with the ids behind every figure (drill to readings, ledger, jobs, money and flags)."""

    readings: list[SheetReadingDto]
    segments: list[SheetSegmentDto]
    money_sources: list[SheetMoneySourceDto]
    flag_records: list[SheetFlagRefDto]
    fuel_events: list[SheetFuelDto]


# --- revenue reasons (tenant list) ------------------------------------------------------------------------------
class RevenueReasonIn(BaseModel):
    code: Code
    name: Name
    description: str | None = Field(default=None, max_length=1000)


class RevenueReasonUpdateIn(RevenueReasonIn):
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class RevenueReasonDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    version: int
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


# --- revenue differences ----------------------------------------------------------------------------------------
class RevenueDifferenceDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    period_kind: str
    period_key: str
    period_start: datetime
    period_end: datetime
    local_from: date
    local_to: date
    job_id: uuid.UUID | None
    job_number: str | None = None
    currency: str
    expected_amount: Decimal
    in_progress_amount: Decimal
    attributed_amount: Decimal
    difference: Decimal
    customer_work_hours: Decimal
    non_revenue_hours: Decimal
    unexplained_hours: Decimal = Field(description="Engine hours outside jobs not approved as non-customer activity")
    unexplained_expected_amount: Decimal = Field(description="Unexplained hours expected as revenue (in expected)")
    detail: dict[str, Any] = Field(description="jobs [{job_id, job_number, expected, attributed}] and money sources")
    status: RevenueDifferenceStatus
    case_id: uuid.UUID | None
    case_number: str | None = None
    policy_version: str
    opened_at: datetime
    computed_at: datetime
    reason_id: uuid.UUID | None
    reason_name: str | None = None
    explanation_note: str | None
    explained_by: uuid.UUID | None
    explained_by_name: str | None = None
    explained_at: datetime | None
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    adjustments: list["RevenueAdjustmentDto"] = Field(
        default_factory=list, description="Later changes recorded against a decided difference (never rewritten)"
    )
    adjusted_difference: Decimal | None = Field(
        default=None, description="difference + the adjustments (null when there are none)"
    )


class RevenueExplanationIn(BaseModel):
    reason_id: uuid.UUID = Field(description="Active entry of the tenant's revenue reason list")
    note: Note


class RevenueDecisionIn(BaseModel):
    decision: Literal["APPROVE", "REJECT", "CONFIRM"] = Field(
        description="APPROVE the proposed explanation (-> EXPLAINED), REJECT it (-> OPEN), or CONFIRM the difference "
        "as real (-> CONFIRMED)"
    )
    note: Note


class RevenueAdjustmentDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    previous_difference: Decimal
    new_difference: Decimal
    amount: Decimal
    cause_type: str = Field(description="engine_hour_classification | non_revenue_approval")
    cause_id: uuid.UUID
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime


# --- non-revenue approvals (owner rule 2026-10-26) --------------------------------------------------------------
class NonRevenueActivityDto(BaseModel):
    """A non-billable work-log entry of a declared non-revenue type, with its explanation/approval status. Until
    APPROVED it counts as revenue."""

    activity_id: uuid.UUID
    job_id: uuid.UUID
    job_number: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    activity_type: str
    started_at: datetime
    ended_at: datetime
    hours: Decimal
    note: str | None
    approval_id: uuid.UUID | None
    approval_status: Literal["NONE", "PROPOSED", "APPROVED", "REJECTED"]


class NonRevenueApprovalIn(BaseModel):
    activity_id: uuid.UUID
    reason_id: uuid.UUID = Field(description="Active entry of the tenant's revenue reason list")
    note: Note


class NonRevenueDecisionIn(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    note: Note


class NonRevenueApprovalDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    activity_id: uuid.UUID
    job_id: uuid.UUID
    job_number: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    activity_type: str
    started_at: datetime
    ended_at: datetime
    hours: Decimal
    reason_id: uuid.UUID
    reason_name: str | None = None
    note: str
    status: str = Field(description="PROPOSED | APPROVED | REJECTED")
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    policy_version: str


RevenueDifferenceDto.model_rebuild()
