"""Daily machine sheet (DEC-031 R2) and the per-machine revenue model shared with the reconciliation (R3).

A read model only: every figure is derived on each call from the engine-hour ledger (readings, job windows,
classifications), the jobs' locked terms, the work log, fuel events, flags (engine-hour exceptions, risk signals),
issued invoice lines and prepaid consumption. Runs in the tenant's RLS scope."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.money import quantize
from asseta.modules.expenses.models import FuelEvent, FuelEventType
from asseta.modules.finance.models import HireInvoiceLine, HireInvoiceStatus, TenantHireInvoice
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.models import HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.intelligence.linking import engine_day_key
from asseta.modules.intelligence.models import AnomalyCase, RiskSignal, RuleCode, SignalStatus
from asseta.modules.jobs.charges import ChargeKind
from asseta.modules.jobs.models import (
    ActivityType,
    Job,
    JobActivity,
    JobStatus,
    RentalContract,
    RentalRatePolicy,
    StandbyTreatment,
)
from asseta.modules.meter.engine_hours import LIVE, MachineLedger, approved_non_revenue_ids, load_machine_ledger
from asseta.modules.meter.ledger import (
    ZERO,
    ActivitySpan,
    LedgerInterval,
    ReadingReview,
    SegmentClassification,
    SegmentKind,
    non_revenue_split,
)
from asseta.modules.meter.models import ExceptionStatus, ExceptionType, JobException, MeterCapture
from asseta.modules.platform_billing.models_commercial import Currency
from asseta.modules.policy.revenue import UnexplainedHoursRateSource, UnexplainedHoursTreatment
from asseta.modules.policy.schemas import BillingMode
from asseta.modules.policy.service import PolicyService
from asseta.modules.revenue.compute import (
    JobTerms,
    MachineRevenue,
    MoneyItem,
    TimeSpan,
    WorkPiece,
    overlap_fraction,
    overlap_hours,
)
from asseta.modules.revenue.dto import (
    DailyMachineSheetDetailDto,
    DailyMachineSheetRowDto,
    SheetFlag,
    SheetFlagRefDto,
    SheetFuelDto,
    SheetJobDto,
    SheetMoneyDto,
    SheetMoneySourceDto,
    SheetReadingDto,
    SheetSegmentDto,
)
from asseta.modules.revenue.models import NonRevenueApproval, RevenueDifference, RevenueDifferenceStatus
from asseta.modules.tenancy.models import TenantSettings

HOURS_STEP = Decimal("0.01")
LITRES_PER_HOUR = Decimal("0.01")
REVENUE_LINE_KINDS = (ChargeKind.HIRE, ChargeKind.STANDBY, ChargeKind.MOBILIZATION, ChargeKind.DISCOUNT)
FUEL_INTO_MACHINE = (FuelEventType.ISSUE, FuelEventType.PURCHASE)


def h(v: Decimal) -> Decimal:
    return v.quantize(HOURS_STEP)


def tenant_zone(s: Session, tenant_id: uuid.UUID) -> ZoneInfo:
    ts = s.get(TenantSettings, tenant_id)
    return ZoneInfo(ts.timezone if ts else "UTC")


def day_window(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    return datetime.combine(day, time(), tz), datetime.combine(day + timedelta(days=1), time(), tz)


@dataclass
class JobMeta:
    job: Job
    customer_id: uuid.UUID | None
    site_id: uuid.UUID | None
    nonbillable: list[str]  # always subtracted from billing
    nonbillable_if_approved: list[str]  # subtracted only for approved entries (owner rule)


@dataclass
class MachineModel:
    """One machine's ledger and revenue facts (load once, slice into any days or periods)."""

    machine: Machine
    ledger: MachineLedger
    jobs: dict[uuid.UUID, JobMeta]
    revenue: MachineRevenue
    deductions: dict[tuple[uuid.UUID, uuid.UUID], Decimal]  # interval key -> non-billable engine hours
    minor_units: dict[str, int] = field(default_factory=dict)
    pending_non_revenue: list[TimeSpan] = field(default_factory=list)  # declared, not yet approved (revenue)

    def revenue_hours(self, i: LedgerInterval) -> Decimal:
        if i.kind is not SegmentKind.CUSTOMER_WORK:
            return ZERO
        return max(i.hours - self.deductions.get(i.key, ZERO), ZERO)

    def money(self, w0: datetime | None, w1: datetime | None) -> list[SheetMoneyDto]:
        out = []
        for currency, w in sorted(self.revenue.window(w0, w1).items()):
            mu = self.minor_units.get(currency, 2)
            expected, progress, attributed = (quantize(v, mu) for v in (w.expected, w.in_progress, w.attributed))
            out.append(
                SheetMoneyDto(
                    currency=currency,
                    expected=expected,
                    in_progress=progress,
                    attributed=attributed,
                    difference=expected - progress - attributed,
                    unexplained_hours=h(w.unexplained_hours),
                    unexplained_expected=quantize(w.unexplained_expected, mu),
                )
            )
        return out


def load_machine_model(s: Session, tenant_id: uuid.UUID, machine: Machine, now: datetime) -> MachineModel:
    ml = load_machine_ledger(s, tenant_id, machine, now)
    job_ids = {i.job_id for i in ml.ledger.intervals if i.job_id is not None}
    job_ids |= set(
        s.execute(
            select(Job.id).where(
                Job.machine_id == machine.id,
                Job.started_at.is_not(None),
                Job.status.in_([JobStatus.IN_PROGRESS, JobStatus.COMPLETED]),
            )
        ).scalars()
    )
    rows = (
        s.execute(
            select(Job, RentalContract.customer_id, RentalContract.job_site_id)
            .join(RentalContract, RentalContract.id == Job.contract_id)
            .where(Job.id.in_(job_ids))
        ).all()
        if job_ids
        else []
    )
    svc = PolicyService(s)
    jobs: dict[uuid.UUID, JobMeta] = {}
    for job, customer_id, contract_site in rows:
        policy = svc.revenue_reconciliation(tenant_id, at=job.started_at or now).policy
        always, approved_only = policy.billing_deductions(job.billing_mode is BillingMode.PREPAID_HOURS)
        jobs[job.id] = JobMeta(job, customer_id, job.job_site_id or contract_site, always, approved_only)
    activities = (
        list(
            s.execute(
                select(JobActivity).where(
                    JobActivity.job_id.in_(jobs.keys()),
                    JobActivity.billable.is_(False),
                    JobActivity.ended_at.is_not(None),
                    JobActivity.activity_type.in_(
                        [ActivityType.DOWNTIME, ActivityType.STANDBY, ActivityType.MOBILIZATION]
                    ),
                )
            ).scalars()
        )
        if jobs
        else []
    )
    approved = (
        set(s.execute(approved_non_revenue_ids().where(NonRevenueApproval.job_id.in_(jobs.keys()))).scalars())
        if jobs
        else set()
    )
    # Non-billable time per job, of the types its billing subtracts (mirrors the job summary's billable hours).
    billing_spans = [
        ActivitySpan(a.job_id, a.activity_type.value, a.started_at, a.ended_at)
        for a in activities
        if a.ended_at is not None
        and (
            a.activity_type.value in jobs[a.job_id].nonbillable
            or (a.activity_type.value in jobs[a.job_id].nonbillable_if_approved and a.id in approved)
        )
    ]
    pending = [  # declared non-revenue entries still counted as revenue (not yet approved)
        a
        for a in activities
        if a.ended_at is not None
        and a.activity_type.value in jobs[a.job_id].nonbillable_if_approved
        and a.id not in approved
    ]
    deductions: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
    pieces: list[WorkPiece] = []
    for i in ml.ledger.intervals:
        if i.kind is not SegmentKind.CUSTOMER_WORK or i.job_id is None or i.job_id not in jobs:
            continue
        cut = sum(non_revenue_split(i.hours, i.start.at, i.end.at, i.job_id, billing_spans).values(), ZERO)
        deductions[i.key] = cut
        pieces.append(WorkPiece(i.job_id, i.start.at, i.end.at, max(i.hours - cut, ZERO)))
    standby = [
        TimeSpan(a.job_id, a.started_at, a.ended_at)
        for a in activities
        if a.ended_at is not None
        and a.activity_type is ActivityType.STANDBY
        and jobs[a.job_id].job.standby_treatment is StandbyTreatment.STANDBY_RATE
    ]
    terms = [
        JobTerms(
            job_id=m.job.id,
            job_number=m.job.job_number,
            customer_id=m.customer_id,
            site_id=m.site_id,
            currency=m.job.currency,
            hourly_rate=m.job.hourly_rate,
            discount_percent=m.job.discount_percent,
            standby_rate=m.job.standby_rate if m.job.standby_treatment is StandbyTreatment.STANDBY_RATE else None,
            mobilization_fee=m.job.mobilization_fee,
            started_at=m.job.started_at or now,
            completed=m.job.status is JobStatus.COMPLETED,
        )
        for m in jobs.values()
    ]
    money = _money_items(s, set(jobs))
    # Owner rule: engine hours outside jobs not approved as non-customer activity are expected revenue.
    unexplained = [
        i
        for i in ml.ledger.intervals
        if i.kind is SegmentKind.UNALLOCATED
        and i.hours > 0
        and i.classification is not SegmentClassification.APPROVED_NON_CUSTOMER
    ]
    rate = unexplained_rate(s, tenant_id, machine, now) if unexplained else None
    currencies = {t.currency for t in terms} | {m.currency for m in money}
    minor = (
        dict(s.execute(select(Currency.code, Currency.minor_units).where(Currency.code.in_(currencies))).all())
        if currencies
        else {}
    )
    revenue = MachineRevenue(
        terms,
        pieces,
        standby,
        money,
        [TimeSpan(uuid.UUID(int=0), i.start.at, i.end.at) for i in unexplained],
        [i.hours for i in unexplained],
        rate,
    )
    model = MachineModel(machine, ml, jobs, revenue, deductions, minor)
    model.pending_non_revenue = [TimeSpan(a.job_id, a.started_at, a.ended_at) for a in pending if a.ended_at]
    return model


def unexplained_rate(s: Session, tenant_id: uuid.UUID, machine: Machine, now: datetime) -> tuple[str, Decimal] | None:
    """(currency, hourly rate) at which unexplained engine hours are expected revenue; None when the tenant excludes
    them (or the machine has no rate card in force)."""
    policy = PolicyService(s).revenue_reconciliation(tenant_id, at=now).policy
    if policy.unexplained_hours_treatment is UnexplainedHoursTreatment.EXCLUDE:
        return None
    if policy.unexplained_hours_rate_source is UnexplainedHoursRateSource.TENANT_RATE:
        ts = s.get(TenantSettings, tenant_id)
        return (ts.currency if ts else "TZS", policy.unexplained_hours_rate or ZERO)
    if machine.category_id is None:
        return None
    card = s.execute(
        select(RentalRatePolicy)
        .where(RentalRatePolicy.machine_category_id == machine.category_id, RentalRatePolicy.effective_from <= now)
        .order_by(RentalRatePolicy.effective_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    return (card.currency, card.hourly_rate) if card else None


def _money_items(s: Session, job_ids: set[uuid.UUID]) -> list[MoneyItem]:
    if not job_ids:
        return []
    items = [
        MoneyItem(line.job_id, "INVOICE_LINE", line.id, inv_id, currency, line.amount, None)
        for line, inv_id, currency in s.execute(
            select(HireInvoiceLine, TenantHireInvoice.id, TenantHireInvoice.currency)
            .join(TenantHireInvoice, TenantHireInvoice.id == HireInvoiceLine.invoice_id)
            .where(
                HireInvoiceLine.job_id.in_(job_ids),
                HireInvoiceLine.kind.in_(REVENUE_LINE_KINDS),
                TenantHireInvoice.status == HireInvoiceStatus.ISSUED,
            )
        ).all()
    ]
    for entry, rate, currency in s.execute(
        select(HoursLedgerEntry, HoursPurchase.effective_rate, HoursPurchase.currency)
        .join(HoursPurchase, HoursPurchase.id == HoursLedgerEntry.purchase_id)
        .where(HoursLedgerEntry.job_id.in_(job_ids), HoursLedgerEntry.entry_type == LedgerEntryType.CONSUMED)
    ).all():
        assert entry.job_id is not None
        items.append(
            MoneyItem(
                entry.job_id,
                "PREPAID_CONSUMPTION",
                entry.id,
                entry.purchase_id,
                currency,
                entry.hours * rate,
                entry.hours,
            )
        )
    return items


# --- the sheet --------------------------------------------------------------------------------------------------
@dataclass
class _Acc:
    engine: Decimal = ZERO
    customer: Decimal = ZERO
    revenue: Decimal = ZERO
    non_revenue: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    approved: Decimal = ZERO
    variance: Decimal = ZERO
    unexplained: Decimal = ZERO
    pending: Decimal = ZERO
    jobs: dict[uuid.UUID, list[Decimal]] = field(default_factory=dict)  # job -> [customer, revenue]


class DailySheet:
    def __init__(self, s: Session, tenant_id: uuid.UUID, now: datetime):
        self._s, self._tid, self._now = s, tenant_id, now
        self.tz = tenant_zone(s, tenant_id)

    def rows(
        self, machines: list[Machine], day_from: date, day_to: date, site_id: uuid.UUID | None = None
    ) -> list[DailyMachineSheetRowDto]:
        out: list[DailyMachineSheetRowDto] = []
        days = [day_from + timedelta(days=n) for n in range((day_to - day_from).days + 1)]
        for m in machines:
            model = load_machine_model(self._s, self._tid, m, self._now)
            facts = _DayFacts(self._s, m.id, *self._range(day_from, day_to))
            for day in days:
                row = self._row(model, facts, day)
                if row is None:
                    continue
                if site_id is not None and site_id not in {j.job_site_id for j in row.jobs}:
                    continue
                out.append(row)
        return sorted(out, key=lambda r: (r.day, r.machine_code or ""), reverse=False)

    def detail(self, machine: Machine, day: date) -> DailyMachineSheetDetailDto:
        model = load_machine_model(self._s, self._tid, machine, self._now)
        facts = _DayFacts(self._s, machine.id, *self._range(day, day))
        row = self._row(model, facts, day, always=True)
        assert row is not None
        d0, d1 = day_window(day, self.tz)
        segments = []
        for i in model.ledger.ledger.intervals:
            f = overlap_fraction(i.start.at, i.end.at, d0, d1)
            if f == 0:
                continue
            segments.append(
                SheetSegmentDto(
                    start_ref=i.start.ref,
                    end_ref=i.end.ref,
                    start_at=i.start.at,
                    end_at=i.end.at,
                    kind=i.kind.value,
                    classification=i.classification.value,
                    review=i.review.value,
                    hours_in_day=h(i.hours * f),
                    customer_work_hours_in_day=h(i.customer_work_hours * f),
                    non_revenue_by_type={t: h(v * f) for t, v in i.non_revenue.items()},
                    job_id=i.job_id,
                    job_number=i.job_number,
                )
            )
        day_jobs = {j.job_id for j in row.jobs}
        sources = [
            SheetMoneySourceDto(
                source=mi.source,
                ref_id=mi.ref_id,
                parent_id=mi.parent_id,
                job_id=mi.job_id,
                job_number=model.jobs[mi.job_id].job.job_number if mi.job_id in model.jobs else None,
                currency=mi.currency,
                amount=mi.amount,
                hours=mi.hours,
            )
            for mi in model.revenue.money
            if mi.job_id in day_jobs
        ]
        return DailyMachineSheetDetailDto(
            **row.model_dump(),
            readings=[
                SheetReadingDto(
                    id=c.id,
                    kind=c.kind.value,
                    captured_at=c.captured_at,
                    reading=c.reading,
                    state=c.state.value,
                    job_id=c.job_id,
                )
                for c in facts.readings.get(day, [])
            ],
            segments=segments,
            money_sources=sources,
            flag_records=list(facts.flag_refs.get(day, [])),
            fuel_events=[
                SheetFuelDto(
                    id=f.id, event_type=f.event_type.value, litres=f.litres, occurred_at=f.occurred_at, job_id=f.job_id
                )
                for f in facts.fuel.get(day, [])
            ],
        )

    def _range(self, day_from: date, day_to: date) -> tuple[datetime, datetime, ZoneInfo]:
        return day_window(day_from, self.tz)[0], day_window(day_to, self.tz)[1], self.tz

    def _row(
        self, model: MachineModel, facts: "_DayFacts", day: date, always: bool = False
    ) -> DailyMachineSheetRowDto | None:
        d0, d1 = day_window(day, self.tz)
        acc = _Acc()
        for i in model.ledger.ledger.intervals:
            f = overlap_fraction(i.start.at, i.end.at, d0, d1)
            if f == 0:
                continue
            acc.engine += i.hours * f
            if i.kind is SegmentKind.CUSTOMER_WORK:
                acc.customer += i.customer_work_hours * f
                acc.revenue += model.revenue_hours(i) * f
                for t, v in i.non_revenue.items():
                    acc.non_revenue[t] += v * f
                if i.job_id is not None:
                    pair = acc.jobs.setdefault(i.job_id, [ZERO, ZERO])
                    pair[0] += i.customer_work_hours * f
                    pair[1] += model.revenue_hours(i) * f
            elif i.review is ReadingReview.PENDING_REVIEW:
                acc.pending += i.hours * f
            elif i.classification is SegmentClassification.APPROVED_NON_CUSTOMER:
                acc.approved += i.hours * f
            elif i.classification is SegmentClassification.IDENTIFIED_VARIANCE:
                acc.variance += i.hours * f
            elif i.classification is SegmentClassification.UNEXPLAINED:
                acc.unexplained += i.hours * f
        for job_id, meta in model.jobs.items():  # jobs running that day without readings inside it yet
            start = meta.job.started_at
            end = meta.job.completed_at
            if start is not None and start < d1 and (end is None or end > d0):
                acc.jobs.setdefault(job_id, [ZERO, ZERO])
        readings = facts.readings.get(day, [])
        flags = sorted({r.flag for r in facts.flag_refs.get(day, [])})
        if acc.unexplained > 0:
            flags = sorted({*flags, SheetFlag.UNEXPLAINED_HOURS})
        fuel = sum((f.litres for f in facts.fuel.get(day, [])), ZERO)
        if not always and not (acc.engine > 0 or readings or acc.jobs or fuel > 0 or flags):
            return None
        money = model.money(d0, d1)
        pending = sum((overlap_hours(p.start, p.end, d0, d1) for p in model.pending_non_revenue), ZERO)
        jobs = [
            SheetJobDto(
                job_id=jid,
                job_number=model.jobs[jid].job.job_number if jid in model.jobs else None,
                customer_id=model.jobs[jid].customer_id if jid in model.jobs else None,
                job_site_id=model.jobs[jid].site_id if jid in model.jobs else None,
                billing_mode=model.jobs[jid].job.billing_mode.value if jid in model.jobs else "",
                status=model.jobs[jid].job.status.value if jid in model.jobs else "",
                customer_work_hours=h(pair[0]),
                revenue_hours=h(pair[1]),
            )
            for jid, pair in sorted(acc.jobs.items(), key=lambda kv: str(kv[0]))
        ]
        return DailyMachineSheetRowDto(
            machine_id=model.machine.id,
            machine_code=model.machine.asset_code,
            machine_name=model.machine.name,
            day=day,
            first_reading=readings[0].reading if readings else None,
            last_reading=readings[-1].reading if readings else None,
            reading_count=len(readings),
            engine_hours=h(acc.engine),
            customer_work_hours=h(acc.customer),
            non_revenue_hours=h(sum(acc.non_revenue.values(), ZERO)),
            non_revenue_by_type={t: h(v) for t, v in sorted(acc.non_revenue.items())},
            non_revenue_pending_hours=h(pending),
            revenue_hours=h(acc.revenue),
            approved_non_customer_hours=h(acc.approved),
            identified_variance_hours=h(acc.variance),
            unexplained_hours=h(acc.unexplained),
            pending_review_hours=h(acc.pending),
            fuel_litres=fuel,
            fuel_litres_per_engine_hour=(fuel / acc.engine).quantize(LITRES_PER_HOUR) if acc.engine > 0 else None,
            jobs=jobs,
            money=money,
            flags=flags,
        )


class _DayFacts:
    """Readings, fuel and flag records of one machine over a day range, bucketed by tenant-local day."""

    def __init__(self, s: Session, machine_id: uuid.UUID, start: datetime, end: datetime, tz: ZoneInfo):
        self.readings: dict[date, list[MeterCapture]] = defaultdict(list)
        self.fuel: dict[date, list[FuelEvent]] = defaultdict(list)
        self.flag_refs: dict[date, list[SheetFlagRefDto]] = defaultdict(list)
        for c in s.execute(
            select(MeterCapture)
            .where(
                MeterCapture.machine_id == machine_id,
                MeterCapture.state.in_(LIVE),
                MeterCapture.captured_at >= start,
                MeterCapture.captured_at < end,
            )
            .order_by(MeterCapture.captured_at, MeterCapture.reading)
        ).scalars():
            self.readings[c.captured_at.astimezone(tz).date()].append(c)
        for f in s.execute(
            select(FuelEvent).where(
                FuelEvent.machine_id == machine_id,
                FuelEvent.event_type.in_(FUEL_INTO_MACHINE),
                FuelEvent.occurred_at >= start,
                FuelEvent.occurred_at < end,
            )
        ).scalars():
            self.fuel[f.occurred_at.astimezone(tz).date()].append(f)
        first, last = start.astimezone(tz).date(), (end - timedelta(microseconds=1)).astimezone(tz).date()
        for e in s.execute(
            select(JobException).where(
                JobException.machine_id == machine_id,
                JobException.exception_type == ExceptionType.MISSING_DAILY_REPORT,
                JobException.status != ExceptionStatus.EXPLAINED,
            )
        ).scalars():
            raw = (e.evidence or {}).get("day")
            try:
                day = date.fromisoformat(str(raw))
            except ValueError:
                continue
            if first <= day <= last:
                self.flag_refs[day].append(
                    SheetFlagRefDto(flag=SheetFlag.MISSING_DAILY_REPORT, record_type="job_exception", record_id=e.id)
                )
        signal_flags = {
            RuleCode.UNREPORTED_ENGINE_ACTIVITY: SheetFlag.ENGINE_ON_WITHOUT_JOB,
            RuleCode.ENGINE_RUNNING_WITHOUT_WORK: SheetFlag.ENGINE_ON_WITHOUT_JOB,
            RuleCode.FUEL_ALLOWANCE_EXCEEDED: SheetFlag.FUEL_ABOVE_NORM,
            RuleCode.MACHINE_FUEL_ABOVE_NORM: SheetFlag.FUEL_ABOVE_NORM,
        }
        for sig in s.execute(
            select(RiskSignal).where(
                RiskSignal.machine_id == machine_id,
                RiskSignal.rule_code.in_(signal_flags),
                RiskSignal.status != SignalStatus.DISMISSED,
                RiskSignal.window_start < end,
                RiskSignal.window_end >= start,
            )
        ).scalars():
            d = max(sig.window_start, start).astimezone(tz).date()
            stop = min(sig.window_end, end - timedelta(microseconds=1)).astimezone(tz).date()
            while d <= stop:
                self.flag_refs[d].append(
                    SheetFlagRefDto(flag=signal_flags[sig.rule_code], record_type="risk_signal", record_id=sig.id)
                )
                d += timedelta(days=1)
        day_keys: dict[str, date] = {}
        d = first
        while d <= last:
            day_keys[engine_day_key(machine_id, d)] = d
            d += timedelta(days=1)
        for case_id, key in s.execute(  # one case per machine-day (S1): the sheet links to it
            select(AnomalyCase.id, AnomalyCase.group_key).where(
                AnomalyCase.machine_id == machine_id, AnomalyCase.group_key.in_(list(day_keys))
            )
        ).all():
            self.flag_refs[day_keys[str(key)]].append(
                SheetFlagRefDto(flag=SheetFlag.ENGINE_ON_WITHOUT_JOB, record_type="anomaly_case", record_id=case_id)
            )
        for diff in s.execute(
            select(RevenueDifference).where(
                RevenueDifference.machine_id == machine_id,
                RevenueDifference.status != RevenueDifferenceStatus.CLEARED,
                RevenueDifference.local_from <= last,
                RevenueDifference.local_to >= first,
            )
        ).scalars():
            d = max(diff.local_from, first)
            while d <= min(diff.local_to, last):
                self.flag_refs[d].append(
                    SheetFlagRefDto(
                        flag=SheetFlag.REVENUE_DIFFERENCE, record_type="revenue_difference", record_id=diff.id
                    )
                )
                d += timedelta(days=1)
