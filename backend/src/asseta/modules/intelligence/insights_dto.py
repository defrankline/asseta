"""Baseline insight and manual-override report DTOs (tenant-facing). Wording is descriptive ("outside this machine's
usual range"), never a judgement about a person; there is no model score here."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

InsightStatus = Literal["READY", "INSUFFICIENT_DATA"]
Trend = Literal["UP", "DOWN", "FLAT"]


class FuelEfficiencyInsightDto(BaseModel):
    machine_id: uuid.UUID
    asset_code: str
    machine_name: str
    status: InsightStatus
    week_ending: datetime | None = Field(description="Week the current value belongs to (tenant-local week end)")
    current_litres_per_hour: float | None
    median_litres_per_hour: float | None = Field(description="Median of this machine's previous weeks")
    band_low: float | None
    band_high: float | None
    outside_usual_range: bool | None = Field(description="Current week outside the machine's robust band")
    weeks_observed: int = Field(description="Previous weeks with both fuel and meter hours")
    min_weeks_required: int
    message: str
    missing: list[str] = Field(description="What is missing for an honest comparison (INSUFFICIENT_DATA)")


class WeeklyHoursDto(BaseModel):
    week_ending: datetime
    hours: float
    source: Literal["meter", "engine", "none"]


class UtilisationInsightDto(BaseModel):
    machine_id: uuid.UUID
    asset_code: str
    machine_name: str
    status: InsightStatus
    hours_per_available_day: float | None
    available_days: int = Field(description="Calendar days in the observed weeks while the machine was registered")
    weeks_observed: int
    min_weeks_required: int
    trend_hours_per_week: float | None = Field(description="Least-squares change in weekly hours per week")
    trend: Trend | None
    weekly: list[WeeklyHoursDto]
    message: str
    missing: list[str]


class CashFlowWeekDto(BaseModel):
    week_start: datetime
    week_end: datetime
    receipts: Decimal = Field(description="Verified customer receipts received in the week")
    expenses: Decimal = Field(description="Approved expenses incurred in the week")
    net: Decimal


class CashFlowInsightDto(BaseModel):
    status: InsightStatus
    currency: str
    weeks: list[CashFlowWeekDto]
    weeks_observed: int
    min_weeks_required: int
    trend_per_week: Decimal | None = Field(description="Least-squares change in weekly net per week")
    trend: Trend | None
    median_weekly_net: Decimal | None
    message: str
    missing: list[str]


class TenantInsightsDto(BaseModel):
    generated_at: datetime
    history_weeks: int = Field(description="Weeks of history considered")
    fuel_efficiency: list[FuelEfficiencyInsightDto]
    utilisation: list[UtilisationInsightDto]
    cash_flow: CashFlowInsightDto | None = Field(description="Present only with tenant.finance.report")
    method: list[str] = Field(description="How each insight is computed, in plain words")


class ManualOverrideItemDto(BaseModel):
    capture_id: uuid.UUID
    captured_at: datetime
    received_at: datetime
    machine_id: uuid.UUID
    asset_code: str
    machine_name: str
    job_id: uuid.UUID
    job_number: str | None
    kind: str
    capture_mode: str
    manually_corrected: bool
    ocr_value: Decimal | None
    entered_value: Decimal
    difference: Decimal | None = Field(description="entered - OCR")
    ocr_confidence: float | None
    ocr_engine: str | None
    captured_by_user_id: uuid.UUID | None
    captured_by_name: str | None
    state: str
    exception_id: uuid.UUID | None = Field(description="The MANUAL_CORRECTION exception raised for review, if any")
    exception_status: str | None


class ManualOverrideSummaryDto(BaseModel):
    total: int
    manual_corrections: int = Field(description="OCR value corrected by the supervisor")
    manual_mode_with_ocr: int = Field(description="Manual-mode captures where an OCR value also existed")
    value_differs: int = Field(description="Entered value differs from the OCR value")
    exceptions_open: int = Field(description="Related MANUAL_CORRECTION exceptions not yet reviewed")


class ManualOverrideReportDto(BaseModel):
    summary: ManualOverrideSummaryDto
    items: list[ManualOverrideItemDto]
    total: int
    page: int
    page_size: int
