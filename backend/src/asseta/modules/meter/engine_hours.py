"""Engine-hour ledger loading and the controls built on it (design B): the START gate (approved baseline, no
overlapping allocation), machine-level flags (UNEXPLAINED_HOURS, OVERLAPPING_ALLOCATION, MISSING_DAILY_REPORT) and
the facts the periodic sweep ages into investigations. Runs in the tenant's RLS scope. Flags are evidence for
review only; nothing here decides anything about a person."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation
from asseta.core.outbox import OutboxWriter
from asseta.modules.fleet.models import Machine
from asseta.modules.jobs.models import ActivityType, Job, JobActivity, JobStatus
from asseta.modules.meter.engine_models import EngineHourClassification, MachineMeterBaseline, MeterProposalStatus
from asseta.modules.meter.ledger import (
    ActivitySpan,
    ClassificationFact,
    JobSpan,
    Ledger,
    LedgerInterval,
    LedgerPoint,
    ResetPoint,
    build_ledger,
    rebased_between,
)
from asseta.modules.meter.models import (
    CaptureState,
    ExceptionStatus,
    ExceptionType,
    JobException,
    MeterCapture,
    MeterResetEvent,
    ReadingKind,
)
from asseta.modules.policy.engine_hours import EngineHoursPolicy
from asseta.modules.policy.service import EffectivePolicy, PolicyService
from asseta.modules.telemetry.models import MachineStateEvent, StateDimension
from asseta.modules.tenancy.models import TenantSettings

LIVE = (CaptureState.ACCEPTED, CaptureState.PROVISIONAL)
TOPIC = "asseta.meter"


@dataclass
class MachineLedger:
    machine: Machine
    baseline: MachineMeterBaseline | None
    proposal: MachineMeterBaseline | None
    ledger: Ledger
    policy: EffectivePolicy[EngineHoursPolicy]

    @property
    def reconciling(self) -> bool:
        """Reconciliation begins at the approved baseline [3.2.1]; before it, intervals are shown, never flagged."""
        return self.baseline is not None

    def open_items(self) -> list[LedgerInterval]:
        if not self.reconciling:
            return []
        floor = self.policy.policy.unexplained_flag_min_hours
        return [i for i in self.ledger.intervals if i.open_item and i.hours > floor]


def approved_baseline(s: Session, machine_id: uuid.UUID) -> MachineMeterBaseline | None:
    return s.execute(
        select(MachineMeterBaseline).where(
            MachineMeterBaseline.machine_id == machine_id, MachineMeterBaseline.status == MeterProposalStatus.APPROVED
        )
    ).scalar_one_or_none()


def pending_baseline(s: Session, machine_id: uuid.UUID) -> MachineMeterBaseline | None:
    return s.execute(
        select(MachineMeterBaseline).where(
            MachineMeterBaseline.machine_id == machine_id, MachineMeterBaseline.status == MeterProposalStatus.PROPOSED
        )
    ).scalar_one_or_none()


def _unverified_capture_ids(s: Session, capture_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Readings with a blocking finding that is still open (or confirmed as a problem)."""
    if not capture_ids:
        return set()
    rows = s.execute(
        select(JobException.meter_capture_id).where(
            JobException.meter_capture_id.in_(capture_ids),
            JobException.blocking.is_(True),
            JobException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.CONFIRMED]),
        )
    ).scalars()
    return {r for r in rows if r is not None}


def load_machine_ledger(s: Session, tenant_id: uuid.UUID, machine: Machine, now: datetime) -> MachineLedger:
    eff = PolicyService(s).engine_hours(tenant_id, machine.id, at=now)
    baseline = approved_baseline(s, machine.id)
    proposal = pending_baseline(s, machine.id)
    stmt = select(MeterCapture).where(MeterCapture.machine_id == machine.id, MeterCapture.state.in_(LIVE))
    if baseline is not None:
        stmt = stmt.where(MeterCapture.captured_at >= baseline.captured_at)
        if baseline.source_capture_id is not None:
            stmt = stmt.where(MeterCapture.id != baseline.source_capture_id)
    captures = list(s.execute(stmt).scalars())
    held = (
        set()
        if eff.policy.ledger_includes_unreviewed_readings
        else _unverified_capture_ids(s, [c.id for c in captures if c.state is CaptureState.PROVISIONAL])
    )
    points = [
        LedgerPoint(c.id, c.kind.value, c.captured_at, c.reading, c.received_at, c.id not in held, c.job_id)
        for c in captures
    ]
    if baseline is not None:
        points.append(
            LedgerPoint(
                baseline.id,
                "BASELINE",
                baseline.captured_at,
                baseline.reading,
                baseline.decided_at or baseline.proposed_at,
                True,
            )
        )
    resets = approved_resets(s, machine.id)
    classifications = [
        ClassificationFact(c.id, c.start_ref, c.end_ref, c.hours, c.status.value, c.outcome.value, c.reason_id)
        for c in s.execute(
            select(EngineHourClassification).where(
                EngineHourClassification.machine_id == machine.id,
                EngineHourClassification.status.in_([MeterProposalStatus.PROPOSED, MeterProposalStatus.APPROVED]),
            )
        ).scalars()
    ]
    spans = job_spans(s, machine.id)
    activities = non_revenue_activities(s, tenant_id, [sp.job_id for sp in spans], now)
    return MachineLedger(
        machine, baseline, proposal, build_ledger(points, resets, spans, classifications, activities), eff
    )


def approved_non_revenue_ids() -> Select[uuid.UUID]:
    from asseta.modules.revenue.models import (  # lazy: revenue builds on meter
        NonRevenueApproval,
        NonRevenueApprovalStatus,
    )

    return select(NonRevenueApproval.activity_id).where(NonRevenueApproval.status == NonRevenueApprovalStatus.APPROVED)


def non_revenue_activities(
    s: Session, tenant_id: uuid.UUID, job_ids: list[uuid.UUID], now: datetime
) -> list[ActivitySpan]:
    """[DEC-031 R1] Non-billable, ended work-log entries of the tenant's declared non-revenue types on these jobs
    (approved ones only, when the tenant requires approval) — only while the tenant's revenue-hour basis is on
    (`deduct_non_revenue_from_working_hours`); none otherwise, so the ledger is exactly as before."""
    policy = PolicyService(s).revenue_reconciliation(tenant_id, at=now).policy.in_force()
    if not policy.deduct_non_revenue_from_working_hours or not policy.non_revenue_activity_types or not job_ids:
        return []
    stmt = select(JobActivity).where(
        JobActivity.job_id.in_(job_ids),
        JobActivity.activity_type.in_(policy.non_revenue_activity_types),
        JobActivity.billable.is_(False),
        JobActivity.ended_at.is_not(None),
    )
    if policy.non_revenue_requires_approval:  # owner rule: non-revenue only once explained and approved
        stmt = stmt.where(JobActivity.id.in_(approved_non_revenue_ids()))
    rows = s.execute(stmt).scalars()
    return [
        ActivitySpan(a.job_id, a.activity_type.value, a.started_at, a.ended_at) for a in rows if a.ended_at is not None
    ]


def approved_resets(s: Session, machine_id: uuid.UUID) -> list[ResetPoint]:
    return [
        ResetPoint(r.effective_at, r.old_reading, r.new_reading)
        for r in s.execute(
            select(MeterResetEvent).where(
                MeterResetEvent.machine_id == machine_id, MeterResetEvent.status == "APPROVED"
            )
        ).scalars()
    ]


def job_spans(s: Session, machine_id: uuid.UUID, exclude: uuid.UUID | None = None) -> list[JobSpan]:
    """Started jobs' engine windows on a machine, from their live opening/closing readings."""
    jobs = s.execute(
        select(Job).where(
            Job.machine_id == machine_id,
            Job.status.in_([JobStatus.IN_PROGRESS, JobStatus.COMPLETED]),
            Job.started_at.is_not(None),
        )
    ).scalars()
    spans = []
    for job in jobs:
        if job.id == exclude:
            continue
        reads = {
            c.kind: c
            for c in s.execute(
                select(MeterCapture).where(
                    MeterCapture.job_id == job.id,
                    MeterCapture.kind.in_([ReadingKind.OPENING, ReadingKind.CLOSING]),
                    MeterCapture.state.in_(LIVE),
                )
            ).scalars()
        }
        opening, closing = reads.get(ReadingKind.OPENING), reads.get(ReadingKind.CLOSING)
        if opening is None:
            continue
        spans.append(
            JobSpan(
                job.id,
                job.job_number,
                opening.captured_at,
                closing.captured_at if closing else None,
                opening.reading,
                closing.reading if closing else None,
            )
        )
    return spans


def engine_hours_on(s: Session, tenant_id: uuid.UUID, at: datetime) -> bool:
    """The tenant's ENGINE_HOURS capability (master switch; tenant level only)."""
    return PolicyService(s).engine_hours(tenant_id, at=at).policy.enabled


# --- job gates ---------------------------------------------------------------------------------------------------
def ensure_job_can_start(s: Session, tenant_id: uuid.UUID, job: Job, opening: MeterCapture, now: datetime) -> None:
    """START controls, each a tenant policy switch: an approved baseline must exist [3.2.1], and the opening reading
    must not fall inside another job's engine interval in time or meter range [3.2.5]. Both off with ENGINE_HOURS."""
    policy = PolicyService(s).engine_hours(tenant_id, job.machine_id, at=now).policy.in_force()
    if policy.baseline_required_before_start and approved_baseline(s, job.machine_id) is None:
        raise BusinessRuleViolation(
            "This machine has no approved meter baseline yet; propose one and have it approved before starting",
            code="BASELINE_REQUIRED",
        )
    if policy.prevent_overlapping_allocation:
        _ensure_no_overlap(s, job, opening.captured_at, opening.reading, None, None)


def ensure_job_can_complete(s: Session, tenant_id: uuid.UUID, job: Job, closing: MeterCapture, now: datetime) -> None:
    """COMPLETE control: the job's whole interval must not overlap another job's [3.2.5]."""
    policy = PolicyService(s).engine_hours(tenant_id, job.machine_id, at=now).policy.in_force()
    if not policy.prevent_overlapping_allocation:
        return
    opening = s.execute(
        select(MeterCapture).where(
            MeterCapture.job_id == job.id, MeterCapture.kind == ReadingKind.OPENING, MeterCapture.state.in_(LIVE)
        )
    ).scalar_one_or_none()
    if opening is not None:
        _ensure_no_overlap(s, job, opening.captured_at, opening.reading, closing.captured_at, closing.reading)


def _ensure_no_overlap(
    s: Session,
    job: Job,
    start: datetime,
    start_reading: Any,
    end: datetime | None,
    end_reading: Any,
) -> None:
    resets = approved_resets(s, job.machine_id)
    for other in job_spans(s, job.machine_id, exclude=job.id):
        other_end = other.end or datetime.max.replace(tzinfo=start.tzinfo)
        mine_end = end or datetime.max.replace(tzinfo=start.tzinfo)
        in_time = start < other_end and other.start < mine_end
        in_range = other.start_reading <= start_reading and (
            other.end_reading is None or start_reading < other.end_reading
        )
        if end_reading is not None and other.end_reading is not None:
            in_range = in_range or (start_reading < other.end_reading and other.start_reading < end_reading)
        in_range = in_range and not rebased_between(resets, other.start, start)
        if in_time or in_range:
            raise BusinessRuleViolation(
                f"These engine hours are already allocated to job {other.job_number}",
                code="OVERLAPPING_ALLOCATION",
            )


def ensure_no_activity_overlap(
    s: Session, tenant_id: uuid.UUID, job: Job, activity_type: str, start: datetime, end: datetime | None
) -> None:
    """[3.2.5] A timed work-log entry may not overlap another timed entry of the same job (an hour logged once).
    Notes and entries without an end are points in time and never overlap. Policy switch per machine."""
    if activity_type == ActivityType.NOTE.value or end is None:
        return
    if not PolicyService(s).engine_hours(tenant_id, job.machine_id).policy.in_force().prevent_overlapping_activity:
        return
    clash = s.execute(
        select(JobActivity.id).where(
            JobActivity.job_id == job.id,
            JobActivity.activity_type != ActivityType.NOTE,
            JobActivity.ended_at.is_not(None),
            JobActivity.started_at < end,
            JobActivity.ended_at > start,
        )
    ).first()
    if clash is not None:
        raise BusinessRuleViolation(
            "This entry overlaps another work-log entry of the job", code="OVERLAPPING_ACTIVITY"
        )


# --- flags -------------------------------------------------------------------------------------------------------
def _segment_evidence(i: LedgerInterval, now: datetime) -> dict[str, Any]:
    return {
        "start_ref": str(i.start.ref),
        "end_ref": str(i.end.ref),
        "start_source": i.start.source,
        "end_source": i.end.source,
        "start_at": i.start.at.isoformat(),
        "end_at": i.end.at.isoformat(),
        "start_reading": str(i.start.reading),
        "end_reading": str(i.end.reading),
        "hours": str(i.hours),
        "opened_at": i.opened_at.isoformat(),
        "age_days": (now - i.opened_at).days,
    }


def unexplained_dedupe(machine_id: uuid.UUID, start_ref: uuid.UUID, end_ref: uuid.UUID) -> str:
    return f"engine:unexplained:{machine_id}:{start_ref}:{end_ref}"


class EngineHoursMonitor:
    """Machine-level engine-hour flags. Nothing is flagged, aged or reminded while the tenant's ENGINE_HOURS
    capability is switched off (job meter readings then work as before these controls)."""

    def __init__(self, s: Session, tenant_id: uuid.UUID, now: datetime):
        self._s, self._tid, self._now = s, tenant_id, now

    def enabled(self) -> bool:
        return engine_hours_on(self._s, self._tid, self._now)

    def _flag(
        self,
        machine_id: uuid.UUID,
        job_id: uuid.UUID | None,
        kind: ExceptionType,
        dedupe: str,
        evidence: dict[str, Any],
    ) -> bool:
        stamp = PolicyService(self._s).engine_hours(self._tid, machine_id, at=self._now).version_stamp
        new_id = self._s.execute(
            insert(JobException)
            .values(
                id=uuid.uuid4(),
                tenant_id=self._tid,
                job_id=job_id,
                machine_id=machine_id,
                meter_capture_id=None,  # machine-level: never shown as a finding on someone's reading
                exception_type=kind,
                severity="WARNING",
                blocking=False,
                dedupe_key=dedupe,
                evidence=evidence,
                policy_version=stamp,
                status=ExceptionStatus.OPEN,
                created_at=self._now,
            )
            .on_conflict_do_nothing(constraint="uq_job_exception_dedupe")
            .returning(JobException.id)
        ).scalar_one_or_none()
        if new_id is not None:
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="EngineHoursFlagRaised",
                key=str(machine_id),
                payload={
                    "exception_id": str(new_id),
                    "exception_type": kind.value,
                    "machine_id": str(machine_id),
                    "job_id": str(job_id) if job_id else None,
                    "hours": evidence.get("hours"),
                    "day": evidence.get("day"),
                },
                tenant_id=self._tid,
            )
        return new_id is not None

    def flag_machine(self, machine_id: uuid.UUID) -> int:
        """UNEXPLAINED_HOURS for each verified unexplained segment and OVERLAPPING_ALLOCATION for each pair of jobs
        sharing engine hours, once each (dedupe). Only after reconciliation began (approved baseline)."""
        machine = self._s.get(Machine, machine_id)
        if machine is None or not self.enabled() or approved_baseline(self._s, machine_id) is None:
            return 0
        ml = load_machine_ledger(self._s, self._tid, machine, self._now)
        raised = 0
        for i in ml.open_items():
            raised += self._flag(
                machine_id,
                None,
                ExceptionType.UNEXPLAINED_HOURS,
                unexplained_dedupe(machine_id, i.start.ref, i.end.ref),
                _segment_evidence(i, self._now),
            )
        for o in ml.ledger.overlaps:
            a, b = sorted([str(o.first_job_id), str(o.second_job_id)])
            raised += self._flag(
                machine_id,
                o.first_job_id,
                ExceptionType.OVERLAPPING_ALLOCATION,
                f"engine:overlap:{a}:{b}",
                {"first_job_id": str(o.first_job_id), "second_job_id": str(o.second_job_id), "basis": o.basis},
            )
        return raised

    def baselined_machines(self) -> list[Machine]:
        if not self.enabled():
            return []
        return list(
            self._s.execute(
                select(Machine).where(
                    exists().where(
                        MachineMeterBaseline.machine_id == Machine.id,
                        MachineMeterBaseline.status == MeterProposalStatus.APPROVED,
                    )
                )
            ).scalars()
        )

    def flag_all(self) -> int:
        return sum(self.flag_machine(m.id) for m in self.baselined_machines())

    def flag_missing_daily_reports(self) -> int:
        raised = 0
        for miss in missing_daily_reports(self._s, self._tid, self._now):
            raised += self._flag(
                miss.machine_id,
                miss.job_id,
                ExceptionType.MISSING_DAILY_REPORT,
                f"engine:daily:{miss.machine_id}:{miss.day.isoformat()}",
                {"day": miss.day.isoformat(), "cutoff_hour": miss.cutoff_hour, "basis": miss.basis},
            )
        return raised


# --- daily operational reports -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class MissingReport:
    machine_id: uuid.UUID
    machine_code: str
    machine_name: str
    day: date
    cutoff_hour: int
    basis: str  # ACTIVE_JOB | ENGINE_ACTIVITY
    job_id: uuid.UUID | None


def missing_daily_reports(s: Session, tenant_id: uuid.UUID, now: datetime) -> list[MissingReport]:
    """Working machines without a reading (DAILY or job reading) before the policy cut-off of a tenant-local day
    whose cut-off has passed (today after the cut-off, and yesterday). Working = a job running during that window,
    or engine-on reported by its tracker in it. Per-machine policy may switch the requirement off."""
    svc = PolicyService(s)
    tenant_policy = svc.engine_hours(tenant_id, at=now).policy
    if not tenant_policy.enabled:
        return []  # ENGINE_HOURS switched off: no daily-report requirement
    settings = s.get(TenantSettings, tenant_id)
    tz = ZoneInfo(settings.timezone if settings else "UTC")
    local = now.astimezone(tz)
    cutoff = tenant_policy.daily_report_cutoff_hour
    days = [local.date() - timedelta(days=1)] + ([local.date()] if local.hour >= cutoff else [])
    out: list[MissingReport] = []
    for day in days:
        start = datetime.combine(day, datetime.min.time(), tz)
        end = start + timedelta(hours=cutoff)
        running = select(Job.machine_id, Job.id).where(
            Job.started_at.is_not(None),
            Job.started_at < end,
            Job.status.in_([JobStatus.IN_PROGRESS, JobStatus.COMPLETED]),
            or_(Job.completed_at.is_(None), Job.completed_at > start),
        )
        working: dict[uuid.UUID, tuple[str, uuid.UUID | None]] = {
            m: ("ACTIVE_JOB", j) for m, j in s.execute(running).tuples()
        }
        engine_on = select(MachineStateEvent.machine_id).where(
            MachineStateEvent.dimension == StateDimension.ENGINE,
            MachineStateEvent.value == "ON",
            MachineStateEvent.event_time >= start,
            MachineStateEvent.event_time < end,
        )
        for m in s.execute(engine_on.distinct()).scalars():
            working.setdefault(m, ("ENGINE_ACTIVITY", None))
        if not working:
            continue
        reported = set(
            s.execute(
                select(MeterCapture.machine_id).where(
                    MeterCapture.machine_id.in_(working.keys()),
                    MeterCapture.state.in_(LIVE),
                    and_(MeterCapture.captured_at >= start, MeterCapture.captured_at < end),
                )
            ).scalars()
        )
        machines = {
            m.id: m for m in s.execute(select(Machine).where(Machine.id.in_(working.keys() - reported))).scalars()
        }
        for machine_id, machine in sorted(machines.items(), key=lambda kv: kv[1].asset_code):
            if not svc.engine_hours(tenant_id, machine_id, at=now).policy.daily_report_required:
                continue
            basis, job_id = working[machine_id]
            out.append(MissingReport(machine_id, machine.asset_code, machine.name, day, cutoff, basis, job_id))
    return out
