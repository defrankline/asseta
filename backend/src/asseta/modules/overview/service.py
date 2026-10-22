"""Tenant overview KPIs, assembled from the modules' own services/queries (fleet map status, receivables, cash
custody, cases) so no business rule is re-implemented here. Every query runs in the caller's tenant RLS scope."""

from collections import Counter
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from asseta.modules.expenses.models import ApprovalRequest, ApprovalStatus, Expense, ExpenseStatus
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.common import ZERO, tenant_settings
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    SettlementStatus,
    SupervisorCashCustody,
    TenantHireInvoice,
)
from asseta.modules.finance.receivables import open_receivables
from asseta.modules.geospatial.fleet_map import Connectivity, FleetMapService, Observed
from asseta.modules.geospatial.models import AlertStatus, TrackingAlert
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.models import AnomalyCase, CaseStatus, RiskSignal
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.jobs.work_state import ReportedWorkState
from asseta.modules.meter.models import CaptureState, ExceptionStatus, JobException, MeterCapture
from asseta.modules.overview.dto import (
    OverviewConnectivityCountsDto,
    OverviewCurrencyMoneyDto,
    OverviewFleetSectionDto,
    OverviewMoneySectionDto,
    OverviewRiskSectionDto,
    OverviewSeverityCountsDto,
    OverviewWorkSectionDto,
    TenantOverviewDto,
)

FLEET, JOBS, FINANCE = "tenant.fleet.read", "tenant.job.read", "tenant.finance.read"
CASES, SIGNALS, APPROVALS, METER = "tenant.case.read", "tenant.signal.read", "tenant.approval.read", "tenant.meter.read"
SECTION_PERMISSIONS = (FLEET, JOBS, FINANCE)  # any one of these opens the overview
SIGNAL_WINDOW = timedelta(days=7)
_CONNECTIVITY_FIELD = {
    Connectivity.LIVE: "live",
    Connectivity.RECENT: "recent",
    Connectivity.STALE: "stale",
    Connectivity.OFFLINE: "offline",
    Connectivity.NEVER_REPORTED: "never",
    Connectivity.NO_TRACKER: "no_tracker",
}


def _latest(*values: datetime | None) -> datetime | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def _severities(rows: list[tuple[str, int]]) -> OverviewSeverityCountsDto:
    counts = {str(sev).lower(): int(n) for sev, n in rows}
    return OverviewSeverityCountsDto(**{k: counts.get(k, 0) for k in ("info", "warning", "critical")})


class OverviewService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def _can(self, code: str) -> bool:
        return code in self._ctx.permissions

    def _max(self, column: InstrumentedAttribute[Any]) -> datetime | None:
        value: datetime | None = self._s.execute(select(func.max(column))).scalar_one()
        return value

    def overview(self) -> TenantOverviewDto:
        tz = tenant_settings(self._s, self._tid).timezone
        return TenantOverviewDto(
            tenant_id=self._tid,
            as_of=self._now,
            timezone=tz,
            fleet=self.fleet() if self._can(FLEET) else None,
            work=self.work() if self._can(JOBS) else None,
            money=self.money(tz) if self._can(FINANCE) else None,
            risk=self.risk() if self._can(CASES) or self._can(SIGNALS) else None,
        )

    # --- sections -----------------------------------------------------------------------------------------------
    def fleet(self) -> OverviewFleetSectionDto:
        rows = FleetMapService(self._s, self._tid).fleet(self._now)
        conn = Counter(_CONNECTIVITY_FIELD[r.connectivity] for r in rows)
        work = Counter(r.reported_work_status for r in rows)
        alerts = self._s.execute(
            select(TrackingAlert.severity, func.count())
            .where(TrackingAlert.status == AlertStatus.OPEN)
            .group_by(TrackingAlert.severity)
        ).tuples()
        return OverviewFleetSectionDto(
            machines=len(rows),
            connectivity=OverviewConnectivityCountsDto(**conn),
            reported_work_state={s.value: work.get(s.value, 0) for s in ReportedWorkState},
            engine_on_verified=sum(1 for r in rows if r.observed_engine is Observed.ON),
            open_alerts=_severities(list(alerts)),
            latest_source_at=_latest(*(r.last_message_at for r in rows), self._max(TrackingAlert.created_at)),
        )

    def work(self) -> OverviewWorkSectionDto:
        by_status = dict(self._s.execute(select(Job.status, func.count()).group_by(Job.status)).tuples().all())
        pending = readings = exceptions = None
        latest = [self._max(Job.updated_at)]
        if self._can(APPROVALS):
            pending = int(
                self._s.execute(
                    select(func.count()).where(ApprovalRequest.status == ApprovalStatus.PENDING)
                ).scalar_one()
            )
            latest.append(self._max(ApprovalRequest.requested_at))
        if self._can(METER):
            readings = int(
                self._s.execute(select(func.count()).where(MeterCapture.state == CaptureState.PROVISIONAL)).scalar_one()
            )
            exceptions = int(
                self._s.execute(select(func.count()).where(JobException.status == ExceptionStatus.OPEN)).scalar_one()
            )
            latest += [self._max(MeterCapture.received_at), self._max(JobException.created_at)]
        return OverviewWorkSectionDto(
            jobs_by_status={s.value: int(by_status.get(s, 0)) for s in JobStatus},
            pending_approvals=pending,
            readings_needing_review=readings,
            open_exceptions=exceptions,
            latest_source_at=_latest(*latest),
        )

    def money(self, tz: str) -> OverviewMoneySectionDto:
        local_now = self._now.astimezone(ZoneInfo(tz))
        month_start = local_now.date().replace(day=1)
        since = datetime.combine(month_start, time.min, ZoneInfo(tz)).astimezone(UTC)
        receivables = {r.currency: r for r in open_receivables(self._s, local_now.date())}
        receipts = self._by_currency(
            select(CustomerPayment.currency, func.sum(CustomerPayment.amount))
            .where(
                CustomerPayment.status == SettlementStatus.VERIFIED,
                CustomerPayment.received_at >= since,
                CustomerPayment.received_at <= self._now,
            )
            .group_by(CustomerPayment.currency)
        )
        expenses = self._by_currency(
            select(Expense.currency, func.sum(Expense.amount))
            .where(
                Expense.status == ExpenseStatus.APPROVED, Expense.incurred_at >= since, Expense.incurred_at <= self._now
            )
            .group_by(Expense.currency)
        )
        cash = CashCustodyService(self._s, self._ctx, self._now).outstanding_by_currency()
        cash = {c: v for c, v in cash.items() if v != 0}  # custody reports zero in the base currency by default
        currencies = sorted({*receivables, *receipts, *expenses, *cash})
        rows = []
        for c in currencies:
            r = receivables.get(c)
            rows.append(
                OverviewCurrencyMoneyDto(
                    currency=c,
                    receivables_outstanding=r.outstanding if r else ZERO,
                    receivables_overdue=r.overdue if r else ZERO,
                    overdue_invoices=r.overdue_invoices if r else 0,
                    verified_receipts_mtd=receipts.get(c, ZERO),
                    approved_expenses_mtd=expenses.get(c, ZERO),
                    cash_with_supervisors=cash.get(c, ZERO),
                )
            )
        latest = _latest(
            self._max(TenantHireInvoice.issued_at),
            self._max(CustomerPayment.recorded_at),
            self._max(CustomerPayment.verified_at),
            self._max(Expense.submitted_at),
            self._max(Expense.decided_at),
            self._max(SupervisorCashCustody.created_at),
            self._max(CashHandover.recorded_at),
        )
        return OverviewMoneySectionDto(month_start=month_start, currencies=rows, latest_source_at=latest)

    def risk(self) -> OverviewRiskSectionDto:
        cases = signals = None
        latest: list[datetime | None] = []
        if self._can(CASES):
            rows = self._s.execute(
                select(AnomalyCase.severity, func.count())
                .where(AnomalyCase.status != CaseStatus.RESOLVED)
                .group_by(AnomalyCase.severity)
            ).tuples()
            cases = _severities(list(rows))
            latest.append(self._max(AnomalyCase.updated_at))
        if self._can(SIGNALS):
            rows = self._s.execute(
                select(RiskSignal.severity, func.count())
                .where(RiskSignal.created_at > self._now - SIGNAL_WINDOW, RiskSignal.created_at <= self._now)
                .group_by(RiskSignal.severity)
            ).tuples()
            signals = _severities(list(rows))
            latest.append(self._max(RiskSignal.created_at))
        return OverviewRiskSectionDto(open_cases=cases, signals_last_7_days=signals, latest_source_at=_latest(*latest))

    def _by_currency(self, stmt: Select[str, Decimal]) -> dict[str, Decimal]:
        rows = self._s.execute(stmt).tuples()
        return {str(c): Decimal(v) for c, v in rows if v is not None}
