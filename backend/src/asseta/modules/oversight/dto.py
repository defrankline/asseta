"""DEC-031 Phase 5 DTOs: the per-person scorecard (M1) and idle machines (M2). Names beside ids are filled by the
`@named` mechanism (staff_member_name, machine_code, machine_report_number, ...)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

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
    refused_attempts: int
    pattern_signals: int = Field(description="REPEATED_PATTERN risk signals about the person in the period")
    items_total: int = Field(description="All items above (list order: most first)")


class ScorecardRecordDto(BaseModel):
    """One item behind a scorecard figure, with the record to open (`record_type` + `record_id`):
    meter_exception -> /tenant/exceptions/{id}, engine_interval -> the machine's engine-hour ledger (no record id),
    tracking_alert -> /tenant/alerts/{id}, cash_remittance_overdue -> /tenant/finance/cash/remittance-overdue/{id},
    cash_variance -> /tenant/finance/cash/variances/{id}, security_event -> /tenant/security-events (id),
    risk_signal -> the case of the signal (case_id in detail)."""

    item: ScorecardItem | Literal["PATTERN_SIGNAL"]
    record_type: str
    record_id: uuid.UUID | None
    at: datetime
    day: date | None
    machine_id: uuid.UUID | None = None
    machine_code: str | None = None
    machine_name: str | None = None
    currency: str | None = None
    amount: Money | None = None
    hours: Decimal | None = None
    status: str | None = None
    near_threshold: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)


class ScorecardDetailDto(BaseModel):
    row: ScorecardRowDto
    records: list[ScorecardRecordDto]


# --- M2 idle machines -----------------------------------------------------------------------------------------
class IdleMachineDto(BaseModel):
    """An active machine with no approved machine-report hours for at least OVERSIGHT.idle_after_days."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    category_id: uuid.UUID | None
    idle_since: datetime = Field(description="End of its last approved report with hours (else when registered)")
    idle_days: int
    last_machine_report_id: uuid.UUID | None = Field(description="Its last approved report with hours")
    last_machine_report_number: str | None = None
    last_engine_activity_at: datetime | None = Field(description="Last tracker engine-on (shown, not counted)")
