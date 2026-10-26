"""DEC-031 Phase 5 DTOs: the per-person scorecard (M1), unbilled work and idle machines (M2) and site check-ins
(M3). Names beside ids are filled by the `@named` mechanism (staff_member_name, machine_code, job_number, ...)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from asseta.modules.meter.dto import GpsIn
from asseta.modules.meter.models import GpsStatus
from asseta.modules.platform_billing.dto import Money
from asseta.modules.policy.schemas import ScorecardItem


# --- M1 scorecard ------------------------------------------------------------------------------------------------
class AmountByCurrencyDto(BaseModel):
    currency: str
    count: int
    amount: Money


class CashHeldDto(BaseModel):
    """Cash the person holds now and has not remitted (beyond approved retentions), oldest part first received at
    `held_since`."""

    currency: str
    amount: Money
    held_since: datetime | None
    held_days: int | None


class ScorecardRowDto(BaseModel):
    """One person's figures for the period. Neutral: counts of items to look at, never a verdict."""

    staff_member_id: uuid.UUID
    staff_member_name: str | None = None
    staff_kind: str
    employee_code: str | None
    is_active: bool
    day_from: date
    day_to: date
    machines: int = Field(description="Machines the person was responsible for in the period (assigned / supervised)")
    daily_reports_missing: int
    daily_reports_late: int = Field(description="A reading came for the day, but after the daily-report cut-off")
    unexplained_hours: Decimal = Field(description="Engine hours still unexplained on the person's machines")
    unexplained_items: int
    alerts: int = Field(description="Tracking alerts on the person's machines in the period")
    alerts_open: int = Field(description="Of those, not yet acknowledged or resolved")
    alerts_acknowledged: int
    avg_hours_to_acknowledge: Decimal | None
    max_hours_to_acknowledge: Decimal | None
    cash_held: list[CashHeldDto] = Field(default_factory=list, description="Now (not limited to the period)")
    cash_held_too_long: int = Field(description="Remittance-overdue flags in the period (cut-off or allowance)")
    cash_differences: int
    cash_difference_totals: list[AmountByCurrencyDto]
    cash_differences_near_threshold: int = Field(
        description="Cash differences at or above OVERSIGHT.near_threshold_percent of the cash case threshold"
    )
    revenue_differences: int
    revenue_difference_totals: list[AmountByCurrencyDto]
    refused_attempts: int
    checkins_missed: int | None = Field(description="Null while site check-ins were never required in the period")
    checkins_made: int
    pattern_signals: int = Field(description="REPEATED_PATTERN risk signals about the person in the period")
    items_total: int = Field(description="All items above (list order: most first)")


class ScorecardRecordDto(BaseModel):
    """One item behind a scorecard figure, with the record to open (`record_type` + `record_id`):
    job_exception -> /tenant/exceptions/{id}, engine_interval -> the machine's engine-hour ledger (no record id),
    tracking_alert -> /tenant/alerts/{id}, cash_remittance_overdue -> /tenant/finance/cash/remittance-overdue/{id},
    cash_variance -> /tenant/finance/cash/variances/{id}, revenue_difference -> /tenant/revenue-differences/{id},
    security_event -> /tenant/security-events (id), site_checkin_slot -> a scheduled check-in not made (no id),
    risk_signal -> the case of the signal (case_id in detail)."""

    item: ScorecardItem | Literal["PATTERN_SIGNAL"]
    record_type: str
    record_id: uuid.UUID | None
    at: datetime
    day: date | None
    machine_id: uuid.UUID | None = None
    machine_code: str | None = None
    machine_name: str | None = None
    job_id: uuid.UUID | None = None
    job_number: str | None = None
    currency: str | None = None
    amount: Money | None = None
    hours: Decimal | None = None
    status: str | None = None
    near_threshold: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)


class ScorecardDetailDto(BaseModel):
    row: ScorecardRowDto
    records: list[ScorecardRecordDto]


# --- M2 unbilled work and idle machines ---------------------------------------------------------------------------
class UnbilledJobDto(BaseModel):
    """A completed, billing-ready job not on an issued invoice for more than OVERSIGHT.unbilled_after_days."""

    job_id: uuid.UUID
    job_number: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    customer_id: uuid.UUID
    customer_name: str | None = None
    job_site_id: uuid.UUID | None
    job_site_name: str | None = None
    supervisor_staff_id: uuid.UUID | None
    supervisor_staff_name: str | None = None
    completed_at: datetime
    days_unbilled: int
    billable_hours: Decimal | None
    currency: str
    total: Money | None = Field(description="What the job is worth under its terms (the invoice would snapshot it)")
    draft_invoice_id: uuid.UUID | None = Field(description="A draft invoice already holds the job (not issued yet)")


class IdleMachineDto(BaseModel):
    """An active machine with no running job and no engine hours for at least OVERSIGHT.idle_after_days."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    category_id: uuid.UUID | None
    idle_since: datetime
    idle_days: int
    last_job_id: uuid.UUID | None
    last_job_number: str | None = None
    last_job_completed_at: datetime | None
    last_engine_activity_at: datetime | None = Field(description="Last meter increase or tracker engine-on")
    planned_job_id: uuid.UUID | None = Field(description="An approved job not started yet")
    planned_job_number: str | None = None


# --- M3 site check-ins --------------------------------------------------------------------------------------------
class SiteCheckinIn(BaseModel):
    """A GPS check-in at the site (also the sync op SITE_CHECKIN payload). Never fabricate coordinates: a failed
    GPS attempt is sent with its status and no coordinates."""

    client_id: uuid.UUID
    captured_at: datetime
    gps: GpsIn
    job_site_id: uuid.UUID | None = None


class SiteCheckinDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    staff_member_id: uuid.UUID
    staff_member_name: str | None = None
    recorded_by: uuid.UUID
    recorded_by_name: str | None = None
    captured_at: datetime
    received_at: datetime
    gps_status: GpsStatus
    latitude: float | None
    longitude: float | None
    accuracy_m: float | None
    job_site_id: uuid.UUID | None
    job_site_name: str | None = None
    job_id: uuid.UUID | None
    job_number: str | None = None
    distance_m: float | None = Field(description="From the site centre (GPS fix and a site only)")
    within_distance: bool | None = Field(
        default=None, description="Against OVERSIGHT.site_checkin_max_distance_m; null when not judged"
    )
    source: str


class CheckinSlotDto(BaseModel):
    """A scheduled check-in: MADE (checkin_id), MISSED, DUE (window open now) or UPCOMING."""

    scheduled_at: datetime
    window_minutes: int
    status: Literal["MADE", "MISSED", "DUE", "UPCOMING"]
    checkin_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    job_number: str | None = None


class MySiteCheckinsDto(BaseModel):
    """The caller's own check-ins and schedule (shown to the person in the app)."""

    required: bool
    times: list[str] = Field(description="Tenant-local HH:MM")
    window_minutes: int
    max_distance_m: int | None
    timezone: str
    day_from: date
    day_to: date
    slots: list[CheckinSlotDto]
    checkins: list[SiteCheckinDto]
