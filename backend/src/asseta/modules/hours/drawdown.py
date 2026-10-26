"""Daily drawdown of prepaid hours (DEC-031 P1, `CUSTOMER_HOURS.drawdown` = DAILY; AT_COMPLETION = today).

For every running PREPAID_HOURS job, each tenant-local day's customer-work hours come from the machine's readings (the
engine-hour ledger's intervals inside the job window, split by wall-clock time), less the job's billing deductions
(DOWNTIME / STANDBY and, when the revenue-hour basis deducts them from prepaid hours, approved non-revenue time —
the same rules the final allocation uses), rounded cumulatively with the tenant's billable-hours increment. Those
hours are drawn provisionally (PROVISIONAL ledger entries per usage day), so the balance is live while the job runs;
a corrected reading gives hours back for its day. The final work execution allocation at completion reverses them
and consumes the job's billable hours, so totals always reconcile; a cancelled job gives everything back.

When the customer has fewer hours than the day needs, the tenant's over-consumption rule applies that day: the hours
not covered are not drawn and the job gets an HOURS_OVERRUN exception (blocking per policy), cleared automatically
when new hours cover the shortfall. The sweep is idempotent: it only writes the difference between what each day
should hold and what it holds.

The same scheduler pass runs the low-balance sweep (P2) and queues customers' low-balance SMS."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor
from asseta.core.db import DbScope, apply_scope
from asseta.core.sms.settings import get_sms_settings
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.engine import HoursEngine, hours_policy, job_customer
from asseta.modules.hours.ledger import ZERO
from asseta.modules.hours.low_balance import LowBalanceMonitor, queue_customer_sms
from asseta.modules.hours.models import SIGN, HoursLedgerEntry, LedgerEntryType
from asseta.modules.jobs.models import Job, JobActivity, JobStatus
from asseta.modules.meter.engine_hours import billing_deduction_filter, load_machine_ledger
from asseta.modules.meter.ledger import SegmentKind
from asseta.modules.meter.rules import billable_hours
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.policy.schemas import BillingMode, HoursDrawdown
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import Tenant, TenantSettings, TenantStatus

log = structlog.get_logger()
SWEEP = AuditActor(None, [], "scheduler")
T = LedgerEntryType


@dataclass
class DrawdownSummary:
    tenants: int = 0
    jobs: int = 0
    drawn_entries: int = 0
    overruns: int = 0
    released_jobs: int = 0
    low_balance_alerts: int = 0
    customer_sms: int = 0
    failures: int = 0


def tenant_zone(s: Session, tenant_id: uuid.UUID) -> ZoneInfo:
    ts = s.get(TenantSettings, tenant_id)
    return ZoneInfo(ts.timezone if ts else "UTC")


def _fraction(start: datetime, end: datetime, w0: datetime, w1: datetime) -> Decimal:
    total = (end - start).total_seconds()
    if total <= 0:
        return Decimal(1) if w0 <= start < w1 else ZERO
    part = (min(end, w1) - max(start, w0)).total_seconds()
    return Decimal(str(part)) / Decimal(str(total)) if part > 0 else ZERO


def _overlap_hours(start: datetime, end: datetime, w0: datetime, w1: datetime) -> Decimal:
    seconds = (min(end, w1) - max(start, w0)).total_seconds()
    return Decimal(str(seconds)) / Decimal(3600) if seconds > 0 else ZERO


def daily_targets(s: Session, tenant_id: uuid.UUID, job: Job, now: datetime, tz: ZoneInfo) -> dict[date, Decimal]:
    """Hours each tenant-local day of the running job should hold (>= 0; cumulative rounding, no minimum hours)."""
    if job.started_at is None:
        return {}
    machine = s.get(Machine, job.machine_id)
    if machine is None:
        return {}
    ledger = load_machine_ledger(s, tenant_id, machine, now).ledger
    pieces = [
        (i.start.at, i.end.at, i.hours)
        for i in ledger.intervals
        if i.job_id == job.id and i.kind is SegmentKind.CUSTOMER_WORK and i.hours > 0
    ]
    deductions = [
        (a.started_at, a.ended_at)
        for a in s.execute(
            select(JobActivity).where(
                JobActivity.job_id == job.id,
                JobActivity.billable.is_(False),
                JobActivity.ended_at.is_not(None),
                billing_deduction_filter(s, tenant_id, job),
            )
        ).scalars()
        if a.ended_at is not None
    ]
    billing = PolicyService(s).hire_billing(tenant_id, at=job.started_at).policy
    first, last = job.started_at.astimezone(tz).date(), now.astimezone(tz).date()
    targets: dict[date, Decimal] = {}
    meter = nonbillable = held = ZERO
    day = first
    while day <= last:
        w0 = datetime.combine(day, time(), tz)
        w1 = datetime.combine(day + timedelta(days=1), time(), tz)
        meter += sum((h * _fraction(a, b, w0, w1) for a, b, h in pieces), ZERO)
        nonbillable += sum((_overlap_hours(a, b, w0, w1) for a, b in deductions), ZERO)
        to_date = billable_hours(meter, nonbillable, ZERO, billing) if meter > 0 else ZERO
        target = max(ZERO, to_date - held)
        targets[day] = target
        held += target
        day += timedelta(days=1)
    return targets


def held_by_day(s: Session, job_id: uuid.UUID) -> dict[date, Decimal]:
    held: dict[date, Decimal] = {}
    for day, t, hours in s.execute(
        select(HoursLedgerEntry.usage_day, HoursLedgerEntry.entry_type, func.sum(HoursLedgerEntry.hours))
        .where(
            HoursLedgerEntry.job_id == job_id,
            HoursLedgerEntry.entry_type.in_([T.PROVISIONAL, T.PROVISIONAL_REVERSED]),
        )
        .group_by(HoursLedgerEntry.usage_day, HoursLedgerEntry.entry_type)
    ):
        if day is not None:
            held[day] = held.get(day, ZERO) - SIGN[t] * Decimal(hours)
    return held


def draw_job(
    engine: HoursEngine, s: Session, tenant_id: uuid.UUID, job: Job, now: datetime, tz: ZoneInfo
) -> tuple[int, bool]:
    """Bring the job's provisional draw up to date; returns (ledger entries written, short of hours)."""
    targets = daily_targets(s, tenant_id, job, now, tz)
    held = held_by_day(s, job.id)
    customer_id = job_customer(s, job)
    written, wanted_total, covered_total = 0, ZERO, ZERO
    short_day: date | None = None
    for day in sorted(set(targets) | set(held)):
        target, have = targets.get(day, ZERO), held.get(day, ZERO)
        if have > target:
            back = engine.give_back(job, have - target, f"Corrected readings for {day.isoformat()}", day=day)
            written += 1 if back > 0 else 0
            have -= back
        elif target > have:
            drawn = engine.draw_day(job, customer_id, day, target - have)
            written += 1 if drawn > 0 else 0
            have += drawn
            if have < target and short_day is None:
                short_day = day
        wanted_total += target
        covered_total += min(have, target)
    if short_day is not None:
        engine.daily_overrun(job, short_day, wanted_total, covered_total)
    else:
        engine.cover_daily_overrun(job)
    if written:
        engine.check_low_balance(customer_id, job.machine_id)
    return written, short_day is not None


def _orphaned_jobs(s: Session) -> list[Job]:
    """Jobs no longer running that still hold provisional hours (e.g. cancelled), to be given back."""
    net = func.sum(
        case((HoursLedgerEntry.entry_type == T.PROVISIONAL, HoursLedgerEntry.hours), else_=-HoursLedgerEntry.hours)
    )
    holding = (
        select(HoursLedgerEntry.job_id)
        .where(HoursLedgerEntry.entry_type.in_([T.PROVISIONAL, T.PROVISIONAL_REVERSED]))
        .group_by(HoursLedgerEntry.job_id)
        .having(net > 0)
    )
    return list(
        s.execute(
            select(Job)
            .where(Job.id.in_(holding), Job.status.not_in([JobStatus.IN_PROGRESS, JobStatus.COMPLETED]))
            .order_by(Job.id)
        ).scalars()
    )


def sweep_tenant(s: Session, tenant_id: uuid.UUID, now: datetime, summary: DrawdownSummary) -> None:
    eff = hours_policy(s, tenant_id, now)
    engine = HoursEngine(s, tenant_id, SWEEP, now)
    for job in _orphaned_jobs(s):  # completed jobs' final allocation already replaced their provisional hours
        engine.release_provisional(job, "Job no longer running")
        summary.released_jobs += 1
    if eff.policy.enabled and eff.policy.drawdown is HoursDrawdown.DAILY:
        tz = tenant_zone(s, tenant_id)
        jobs = s.execute(
            select(Job)
            .where(
                Job.status == JobStatus.IN_PROGRESS,
                Job.billing_mode == BillingMode.PREPAID_HOURS,
                Job.started_at.is_not(None),
            )
            .order_by(Job.id)
            .with_for_update()
        ).scalars()
        for job in jobs:
            summary.jobs += 1
            written, short = draw_job(engine, s, tenant_id, job, now, tz)
            summary.drawn_entries += written
            summary.overruns += 1 if short else 0
    summary.low_balance_alerts += LowBalanceMonitor(s, tenant_id, now, eff).sweep()


def run_hours_drawdown(session_factory: Callable[[], Session], now: datetime) -> DrawdownSummary:
    """One pass over every non-closed tenant; one tenant's failure never blocks the others."""
    summary = DrawdownSummary()
    sms, cfg = get_sms_settings(), get_notification_settings()
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        summary.tenants += 1
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                sweep_tenant(s, tid, now, summary)
                apply_scope(s, DbScope.SYSTEM, None, None)
                summary.customer_sms += queue_customer_sms(s, tid, now, sms.sms_default_country_code, cfg.sms_max_chars)
        except Exception:
            log.exception("hours_drawdown_tenant_failed", tenant_id=str(tid))
            summary.failures += 1
    log.info("hours_drawdown_completed", **summary.__dict__)
    return summary
