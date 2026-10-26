"""Per-person scorecard read model (DEC-031 M1). Derived on every call from existing records — no new ledger, no
stored score: missing / late daily-report exceptions, engine hours still unexplained in the engine-hour ledger,
tracking alerts, remittance-overdue flags, cash variances, revenue differences, refused attempts and (M3) scheduled
site check-ins not made.

A person's machines are those they were assigned to (machine assignment, any role) or whose job they supervised,
for the time they were; machine-related items count for every person responsible at the time of the item. Cash items
belong to the custodian, refused attempts to the person whose login made them. Neutral: an item is something to look
at, never a verdict about the person."""

import itertools
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from asseta.modules.accountability.models import SecurityEvent
from asseta.modules.finance.custody_models import CashVariance, RemittanceOverdue
from asseta.modules.fleet.models import Machine, MachineAssignment, StaffMember
from asseta.modules.geospatial.models import AlertStatus, TrackingAlert
from asseta.modules.identity.models import AppUser
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.meter.engine_hours import LIVE, load_machine_ledger, unexplained_dedupe
from asseta.modules.meter.models import ExceptionStatus, ExceptionType, JobException, MeterCapture
from asseta.modules.oversight.models import SiteCheckin
from asseta.modules.policy.capabilities import ENGINE_HOURS, capability_on
from asseta.modules.policy.models import PolicyVersion
from asseta.modules.policy.schemas import OversightPolicy, PolicyScope, PolicyType, ScorecardItem
from asseta.modules.policy.service import PolicyService
from asseta.modules.revenue.models import RevenueDifference, RevenueDifferenceStatus
from asseta.modules.tenancy.models import TenantSettings

EPSILON = timedelta(microseconds=1)
HOURS = Decimal("0.01")


@dataclass(frozen=True)
class Window:
    """A person responsible for a machine over [start, end) (end None = still)."""

    staff_id: uuid.UUID
    start: datetime
    end: datetime | None
    job_id: uuid.UUID | None = None


@dataclass
class ScoreRecord:
    item: ScorecardItem
    record_type: str  # the record behind the item (drill-down); see dto.ScorecardRecordDto
    record_id: uuid.UUID | None
    at: datetime
    machine_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    day: date | None = None
    currency: str | None = None
    amount: Decimal | None = None
    hours: Decimal | None = None
    status: str | None = None
    near_threshold: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Slot:
    """One scheduled check-in a person owed: at `at` (tenant-local time of day), within +/- window."""

    staff_id: uuid.UUID
    at: datetime
    window: timedelta
    job_id: uuid.UUID | None


def tenant_tz(s: Session, tenant_id: uuid.UUID) -> ZoneInfo:
    settings = s.get(TenantSettings, tenant_id)
    return ZoneInfo(settings.timezone if settings else "UTC")


def day_bounds(tz: ZoneInfo, first: date, last: date) -> tuple[datetime, datetime]:
    return datetime.combine(first, time.min, tz), datetime.combine(last + timedelta(days=1), time.min, tz)


def _overlaps(w: Window, start: datetime, end: datetime) -> bool:
    return w.start < end and (w.end is None or w.end > start)


class ScorecardBuilder:
    """Collects every scorecard item of a tenant-local period per person (tenant RLS scope)."""

    def __init__(self, s: Session, tenant_id: uuid.UUID, now: datetime):
        self._s, self._tid, self._now = s, tenant_id, now
        self.tz = tenant_tz(s, tenant_id)
        self._policies = PolicyService(s)
        self.policy: OversightPolicy = self._policies.oversight(tenant_id, at=now).policy
        self._windows: dict[uuid.UUID, list[Window]] = defaultdict(list)
        self._supervised: list[tuple[uuid.UUID, Window]] = []  # (machine, window) of supervised running jobs

    # --- responsibility -------------------------------------------------------------------------------------------
    def _load_windows(self, start: datetime, end: datetime) -> None:
        self._windows.clear()
        self._supervised.clear()
        for a in self._s.execute(
            select(MachineAssignment).where(
                MachineAssignment.effective_from < end,
                or_(MachineAssignment.effective_to.is_(None), MachineAssignment.effective_to > start),
            )
        ).scalars():
            self._windows[a.machine_id].append(Window(a.staff_member_id, a.effective_from, a.effective_to))
        for job_id, machine_id, supervisor, started, completed in self._s.execute(
            select(Job.id, Job.machine_id, Job.supervisor_id, Job.started_at, Job.completed_at).where(
                Job.supervisor_id.is_not(None),
                Job.started_at.is_not(None),
                Job.started_at < end,
                Job.status.in_([JobStatus.IN_PROGRESS, JobStatus.COMPLETED]),
                or_(Job.completed_at.is_(None), Job.completed_at > start),
            )
        ).all():
            assert supervisor is not None and started is not None
            w = Window(supervisor, started, completed, job_id)
            self._windows[machine_id].append(w)
            self._supervised.append((machine_id, w))

    def responsible(self, machine_id: uuid.UUID, start: datetime, end: datetime | None = None) -> set[uuid.UUID]:
        """People responsible for the machine at any time in [start, end) (an instant when end is None)."""
        stop = end if end is not None and end > start else start + EPSILON
        return {w.staff_id for w in self._windows.get(machine_id, []) if _overlaps(w, start, stop)}

    def people_at_site(self, site_id: uuid.UUID, start: datetime, end: datetime) -> set[uuid.UUID]:
        """People who supervised or were assigned to a machine working a job at the site in the period, or checked
        in there (the list's site filter)."""
        jobs = self._s.execute(
            select(Job.machine_id, Job.started_at, Job.completed_at).where(
                Job.job_site_id == site_id,
                Job.started_at.is_not(None),
                Job.started_at < end,
                or_(Job.completed_at.is_(None), Job.completed_at > start),
            )
        ).all()
        out: set[uuid.UUID] = set()
        for machine_id, started, completed in jobs:
            assert started is not None
            out |= self.responsible(machine_id, max(started, start), min(completed or end, end))
        out |= set(
            self._s.execute(
                select(SiteCheckin.staff_member_id).where(
                    SiteCheckin.job_site_id == site_id,
                    SiteCheckin.captured_at >= start,
                    SiteCheckin.captured_at < end,
                )
            ).scalars()
        )
        return out

    # --- collection -----------------------------------------------------------------------------------------------
    def collect(self, day_from: date, day_to: date) -> dict[uuid.UUID, list[ScoreRecord]]:
        start, end = day_bounds(self.tz, day_from, day_to)
        return self.collect_range(start, min(end, self._now) if self._now > start else end)

    def collect_range(self, start: datetime, end: datetime) -> dict[uuid.UUID, list[ScoreRecord]]:
        self._load_windows(start, end)
        out: dict[uuid.UUID, list[ScoreRecord]] = defaultdict(list)

        def add(people: Iterable[uuid.UUID], rec: ScoreRecord) -> None:
            for p in people:
                out[p].append(rec)

        for people, rec in [
            *self._daily_reports(start, end),
            *self._unexplained(start, end),
            *self._alerts(start, end),
            *self._revenue(start, end),
        ]:
            add(people, rec)
        for staff_id, rec in [
            *self._cash_overdue(start, end),
            *self._cash_differences(start, end),
            *self._refused(start, end),
            *self._missed_checkins(start, end),
        ]:
            out[staff_id].append(rec)
        for recs in out.values():
            recs.sort(key=lambda r: (r.at, str(r.record_id)))
        return out

    def _daily_reports(self, start: datetime, end: datetime) -> list[tuple[set[uuid.UUID], ScoreRecord]]:
        first, last = start.astimezone(self.tz).date(), (end - EPSILON).astimezone(self.tz).date()
        out = []
        for e in self._s.execute(
            select(JobException).where(
                JobException.exception_type == ExceptionType.MISSING_DAILY_REPORT,
                JobException.status != ExceptionStatus.EXPLAINED,
            )
        ).scalars():
            try:
                day = date.fromisoformat(str((e.evidence or {}).get("day")))
            except ValueError:
                continue
            if not first <= day <= last:
                continue
            day_start, day_end = day_bounds(self.tz, day, day)
            reported_at = self._s.execute(
                select(MeterCapture.captured_at)
                .where(
                    MeterCapture.machine_id == e.machine_id,
                    MeterCapture.state.in_(LIVE),
                    MeterCapture.captured_at >= day_start,
                    MeterCapture.captured_at < day_end,
                )
                .order_by(MeterCapture.captured_at)
                .limit(1)
            ).scalar_one_or_none()
            item = ScorecardItem.LATE_DAILY_REPORT if reported_at else ScorecardItem.MISSING_DAILY_REPORT
            rec = ScoreRecord(
                item,
                "job_exception",
                e.id,
                day_start,
                machine_id=e.machine_id,
                job_id=e.job_id,
                day=day,
                status=e.status.value,
                detail={
                    "cutoff_hour": (e.evidence or {}).get("cutoff_hour"),
                    "reported_at": reported_at.isoformat() if reported_at else None,
                },
            )
            out.append((self.responsible(e.machine_id, day_start, day_end), rec))
        return out

    def _unexplained(self, start: datetime, end: datetime) -> list[tuple[set[uuid.UUID], ScoreRecord]]:
        if not capability_on(self._s, self._tid, ENGINE_HOURS, self._now):
            return []
        out = []
        for machine_id in list(self._windows):
            machine = self._s.get(Machine, machine_id)
            if machine is None:
                continue
            ledger = load_machine_ledger(self._s, self._tid, machine, self._now)
            for i in ledger.open_items():
                if not (i.start.at < end and i.end.at > start):
                    continue
                people = self.responsible(machine_id, i.start.at, i.end.at)
                if not people:
                    continue
                flag = self._s.execute(
                    select(JobException.id).where(
                        JobException.dedupe_key == unexplained_dedupe(machine_id, i.start.ref, i.end.ref)
                    )
                ).scalar_one_or_none()
                rec = ScoreRecord(
                    ScorecardItem.UNEXPLAINED_HOURS,
                    "job_exception" if flag else "engine_interval",
                    flag,
                    i.start.at,
                    machine_id=machine_id,
                    day=i.start.at.astimezone(self.tz).date(),
                    hours=i.hours.quantize(HOURS),
                    detail={
                        "start_at": i.start.at.isoformat(),
                        "end_at": i.end.at.isoformat(),
                        "start_ref": str(i.start.ref),
                        "end_ref": str(i.end.ref),
                    },
                )
                out.append((people, rec))
        return out

    def _alerts(self, start: datetime, end: datetime) -> list[tuple[set[uuid.UUID], ScoreRecord]]:
        if not self._windows:
            return []
        out = []
        for a in self._s.execute(
            select(TrackingAlert).where(
                TrackingAlert.machine_id.in_(list(self._windows)),
                TrackingAlert.event_time >= start,
                TrackingAlert.event_time < end,
                TrackingAlert.status != AlertStatus.SUPERSEDED,
            )
        ).scalars():
            assert a.machine_id is not None
            people = self.responsible(a.machine_id, a.event_time)
            if not people:
                continue
            ack = (
                (Decimal((a.acknowledged_at - a.event_time).total_seconds()) / 3600).quantize(HOURS)
                if a.acknowledged_at
                else None
            )
            rec = ScoreRecord(
                ScorecardItem.ALERT,
                "tracking_alert",
                a.id,
                a.event_time,
                machine_id=a.machine_id,
                day=a.event_time.astimezone(self.tz).date(),
                hours=ack,
                status=a.status.value,
                detail={"alert_type": a.alert_type.value, "title": a.title, "hours_to_acknowledge": _s(ack)},
            )
            out.append((people, rec))
        return out

    def _revenue(self, start: datetime, end: datetime) -> list[tuple[set[uuid.UUID], ScoreRecord]]:
        out = []
        for d in self._s.execute(
            select(RevenueDifference).where(
                RevenueDifference.period_start < end,
                RevenueDifference.period_end > start,
                RevenueDifference.status != RevenueDifferenceStatus.CLEARED,
            )
        ).scalars():
            people = self.responsible(d.machine_id, d.period_start, d.period_end)
            if not people:
                continue
            rec = ScoreRecord(
                ScorecardItem.REVENUE_DIFFERENCE,
                "revenue_difference",
                d.id,
                d.period_start,
                machine_id=d.machine_id,
                job_id=d.job_id,
                day=d.local_from,
                currency=d.currency,
                amount=d.difference,
                status=d.status.value,
                detail={"period_key": d.period_key, "local_to": d.local_to.isoformat()},
            )
            out.append((people, rec))
        return out

    def _cash_overdue(self, start: datetime, end: datetime) -> list[tuple[uuid.UUID, ScoreRecord]]:
        first, last = start.astimezone(self.tz).date(), (end - EPSILON).astimezone(self.tz).date()
        return [
            (
                o.staff_member_id,
                ScoreRecord(
                    ScorecardItem.CASH_HELD_TOO_LONG,
                    "cash_remittance_overdue",
                    o.id,
                    o.flagged_at,
                    day=o.local_day,
                    status=o.reason.value,
                    detail={
                        "amounts": o.amounts,
                        "held_since": o.held_since.isoformat() if o.held_since else None,
                    },
                ),
            )
            for o in self._s.execute(
                select(RemittanceOverdue).where(
                    RemittanceOverdue.local_day >= first, RemittanceOverdue.local_day <= last
                )
            ).scalars()
        ]

    def _cash_differences(self, start: datetime, end: datetime) -> list[tuple[uuid.UUID, ScoreRecord]]:
        threshold = self._policies.cash_custody(self._tid, at=self._now).policy.in_force().variance_case_threshold
        pct = self.policy.near_threshold_percent
        lower = threshold * pct / 100 if threshold is not None and threshold > 0 and pct is not None else None
        out = []
        for v in self._s.execute(
            select(CashVariance).where(
                CashVariance.staff_member_id.is_not(None),
                CashVariance.opened_at >= start,
                CashVariance.opened_at < end,
            )
        ).scalars():
            assert v.staff_member_id is not None
            near = lower is not None and threshold is not None and lower <= abs(v.amount) <= threshold
            out.append(
                (
                    v.staff_member_id,
                    ScoreRecord(
                        ScorecardItem.CASH_DIFFERENCE,
                        "cash_variance",
                        v.id,
                        v.opened_at,
                        day=v.opened_at.astimezone(self.tz).date(),
                        currency=v.currency,
                        amount=v.amount,
                        status=v.status.value,
                        near_threshold=near,
                        detail={"source_type": v.source_type.value, "case_threshold": _s(threshold)},
                    ),
                )
            )
        return out

    def _refused(self, start: datetime, end: datetime) -> list[tuple[uuid.UUID, ScoreRecord]]:
        by_subject = dict(
            self._s.execute(
                select(StaffMember.keycloak_subject, StaffMember.id).where(StaffMember.keycloak_subject.is_not(None))
            ).all()
        )
        if not by_subject:
            return []
        user_subject = dict(
            self._s.execute(
                select(AppUser.id, AppUser.keycloak_subject).where(AppUser.keycloak_subject.in_(list(by_subject)))
            ).all()
        )
        out = []
        for e in self._s.execute(
            select(SecurityEvent).where(SecurityEvent.occurred_at >= start, SecurityEvent.occurred_at < end)
        ).scalars():
            subject = e.actor_subject or (user_subject.get(e.actor_user_id) if e.actor_user_id else None)
            staff_id = by_subject.get(subject) if subject else None
            if staff_id is None:
                continue
            out.append(
                (
                    staff_id,
                    ScoreRecord(
                        ScorecardItem.REFUSED_ATTEMPT,
                        "security_event",
                        e.id,
                        e.occurred_at,
                        day=e.occurred_at.astimezone(self.tz).date(),
                        status=e.kind.value,
                        detail={"permission": e.permission, "action": e.action, "entity_type": e.entity_type},
                    ),
                )
            )
        return out

    # --- site check-ins (M3) --------------------------------------------------------------------------------------
    def segments(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime, OversightPolicy]]:
        """The OVERSIGHT policy in force over [start, end), split where a platform or tenant version takes effect."""
        changes = sorted(
            set(
                self._s.execute(
                    select(PolicyVersion.effective_from).where(
                        PolicyVersion.policy_type == PolicyType.OVERSIGHT,
                        PolicyVersion.scope.in_([PolicyScope.PLATFORM, PolicyScope.TENANT]),
                        or_(PolicyVersion.tenant_id.is_(None), PolicyVersion.tenant_id == self._tid),
                        PolicyVersion.effective_from > start,
                        PolicyVersion.effective_from < end,
                    )
                ).scalars()
            )
        )
        bounds = [start, *changes, end]
        return [(a, b, self._policies.oversight(self._tid, at=a).policy) for a, b in itertools.pairwise(bounds)]

    def slots(self, start: datetime, end: datetime, staff_id: uuid.UUID | None = None) -> list[Slot]:
        """Scheduled check-ins owed in [start, end): at each configured time while check-ins were required, by every
        supervisor running a job at that moment. Windows must already be loaded for the range."""
        out: list[Slot] = []
        for seg_start, seg_end, policy in self.segments(start, end):
            if not policy.site_checkin_required or not policy.site_checkin_times:
                continue
            window = timedelta(minutes=policy.site_checkin_window_minutes)
            day = seg_start.astimezone(self.tz).date()
            while datetime.combine(day, time.min, self.tz) < seg_end:
                for t in sorted(policy.site_checkin_times):
                    at = datetime.combine(day, t, self.tz)
                    if not seg_start <= at < seg_end:
                        continue
                    owed: dict[uuid.UUID, uuid.UUID | None] = {}
                    for _, w in self._supervised:
                        if (staff_id is None or w.staff_id == staff_id) and _overlaps(w, at, at + EPSILON):
                            owed.setdefault(w.staff_id, w.job_id)
                    out += [Slot(p, at, window, job) for p, job in owed.items()]
                day += timedelta(days=1)
        return out

    def _missed_checkins(self, start: datetime, end: datetime) -> list[tuple[uuid.UUID, ScoreRecord]]:
        slots = [s for s in self.slots(start, end) if s.at + s.window <= self._now]
        if not slots:
            return []
        made = self.checkins(min(s.at - s.window for s in slots), max(s.at + s.window for s in slots))
        out = []
        for slot in slots:
            if any(
                slot.at - slot.window <= c.captured_at <= slot.at + slot.window for c in made.get(slot.staff_id, [])
            ):
                continue
            out.append(
                (
                    slot.staff_id,
                    ScoreRecord(
                        ScorecardItem.MISSED_CHECKIN,
                        "site_checkin_slot",
                        None,
                        slot.at,
                        job_id=slot.job_id,
                        day=slot.at.astimezone(self.tz).date(),
                        status="MISSED",
                        detail={
                            "scheduled_at": slot.at.isoformat(),
                            "window_minutes": int(slot.window.total_seconds() // 60),
                        },
                    ),
                )
            )
        return out

    def checkins(self, start: datetime, end: datetime) -> dict[uuid.UUID, list[SiteCheckin]]:
        out: dict[uuid.UUID, list[SiteCheckin]] = defaultdict(list)
        for c in self._s.execute(
            select(SiteCheckin)
            .where(SiteCheckin.captured_at >= start, SiteCheckin.captured_at <= end)
            .order_by(SiteCheckin.captured_at)
        ).scalars():
            out[c.staff_member_id].append(c)
        return out

    def load_windows(self, start: datetime, end: datetime) -> None:
        self._load_windows(start, end)

    def machines_of(self, staff_id: uuid.UUID) -> set[uuid.UUID]:
        """Machines the person was responsible for in the loaded range."""
        return {m for m, ws in self._windows.items() if any(w.staff_id == staff_id for w in ws)}


def _s(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
