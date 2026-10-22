"""Tenant overview KPI DTOs (owner apps + console dashboard). Each section is present only when the caller holds its
permission; `latest_source_at` is the newest source record behind the section so offline clients can show staleness
of a cached snapshot honestly (it is NOT the time the numbers were computed — that is `as_of`)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from asseta.modules.platform_billing.dto import Money


class OverviewSeverityCountsDto(BaseModel):
    info: int = 0
    warning: int = 0
    critical: int = 0


class OverviewConnectivityCountsDto(BaseModel):
    """Machines by tracker connectivity (thresholds from each machine's effective tracking policy)."""

    live: int = 0
    recent: int = 0
    stale: int = 0
    offline: int = 0
    never: int = Field(default=0, description="Tracker installed but never reported")
    no_tracker: int = 0


class OverviewFleetSectionDto(BaseModel):
    machines: int = Field(description="Registered machines, excluding disposed ones")
    connectivity: OverviewConnectivityCountsDto
    reported_work_state: dict[str, int] = Field(
        description="Machines by supervisor-reported state (ReportedWorkState values, zero-filled)"
    )
    engine_on_verified: int = Field(
        description="Machines whose verified ignition input reports ON with a fresh position (never inferred)"
    )
    open_alerts: OverviewSeverityCountsDto
    latest_source_at: datetime | None = Field(description="Newest tracker message or alert behind this section")


class OverviewWorkSectionDto(BaseModel):
    jobs_by_status: dict[str, int] = Field(description="JobStatus values, zero-filled")
    pending_approvals: int | None = Field(description="Approval requests waiting; null without tenant.approval.read")
    readings_needing_review: int | None = Field(
        description="Provisional meter readings (open exceptions to review); null without tenant.meter.read"
    )
    open_exceptions: int | None = Field(description="Open meter/GPS exceptions; null without tenant.meter.read")
    latest_source_at: datetime | None


class OverviewCurrencyMoneyDto(BaseModel):
    currency: str
    receivables_outstanding: Money = Field(description="Unpaid balance of issued customer invoices")
    receivables_overdue: Money = Field(description="Part of the outstanding balance past its due date")
    overdue_invoices: int
    verified_receipts_mtd: Money = Field(description="Verified customer payments received this tenant-local month")
    approved_expenses_mtd: Money = Field(description="Approved expenses incurred this tenant-local month")
    cash_with_supervisors: Money = Field(description="Cash custody outstanding across all custodians now")


class OverviewMoneySectionDto(BaseModel):
    month_start: date = Field(description="First day of the current month in the tenant's timezone")
    currencies: list[OverviewCurrencyMoneyDto]
    latest_source_at: datetime | None


class OverviewRiskSectionDto(BaseModel):
    open_cases: OverviewSeverityCountsDto | None = Field(description="Unresolved cases; null without tenant.case.read")
    signals_last_7_days: OverviewSeverityCountsDto | None = Field(
        description="Risk signals raised in the last 7 days; null without tenant.signal.read"
    )
    latest_source_at: datetime | None


class TenantOverviewDto(BaseModel):
    tenant_id: uuid.UUID
    as_of: datetime = Field(description="When the overview was computed (UTC)")
    timezone: str = Field(description="Tenant timezone for rendering dates and the month boundary")
    fleet: OverviewFleetSectionDto | None = Field(description="Present with tenant.fleet.read")
    work: OverviewWorkSectionDto | None = Field(description="Present with tenant.job.read")
    money: OverviewMoneySectionDto | None = Field(description="Present with tenant.finance.read")
    risk: OverviewRiskSectionDto | None = Field(description="Present with tenant.case.read or tenant.signal.read")
