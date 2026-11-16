"""Engine-hour ledger loading and the controls built on it (design B): machine-level flags (UNEXPLAINED_HOURS,
MISSING_DAILY_REPORT, DUPLICATE_DAILY_REPORT) and the facts the periodic sweep ages into investigations. Hours inside a
submitted or approved machine report are accounted for by the report (ADR-008). Runs in the tenant's RLS scope. Flags
are evidence for review only; nothing here decides anything about a person."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.outbox import OutboxWriter
from asseta.modules.fleet.models import Machine
from asseta.modules.machine_reports.models import MachineReport, MachineReportStatus
from asseta.modules.meter.allocation_models import DailyOperationalReport
from asseta.modules.meter.engine_models import EngineHourClassification, MachineMeterBaseline, MeterProposalStatus
from asseta.modules.meter.ledger import (
    ClassificationFact,
    Ledger,
    LedgerInterval,
    LedgerPoint,
    ReportSpan,
    ResetPoint,
    build_ledger,
)
from asseta.modules.meter.models import (
    CaptureState,
    ExceptionStatus,
    ExceptionType,
    MeterCapture,
    MeterException,
    MeterResetEvent,
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
        return [i for i in self.ledger.intervals if i.open_item and i.explainable_hours > floor]


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
        select(MeterException.meter_capture_id).where(
            MeterException.meter_capture_id.in_(capture_ids),
            MeterException.blocking.is_(True),
            MeterException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.CONFIRMED]),
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
        LedgerPoint(c.id, c.kind.value, c.captured_at, c.reading, c.received_at, c.id not in held) for c in captures
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
    ledger = build_ledger(points, resets, report_spans(s, machine.id), classifications)
    return MachineLedger(machine, baseline, proposal, ledger, eff)


def report_spans(s: Session, machine_id: uuid.UUID) -> list[ReportSpan]:
    """The periods of the machine's submitted and approved machine reports (they account for those hours)."""
    return [
        ReportSpan(r.id, r.report_number, r.start_at, r.end_at)
        for r in s.execute(
            select(MachineReport).where(
                MachineReport.machine_id == machine_id,
                MachineReport.status.in_([MachineReportStatus.SUBMITTED, MachineReportStatus.APPROVED]),
                MachineReport.hours > 0,
            )
        ).scalars()
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


def engine_hours_on(s: Session, tenant_id: uuid.UUID, at: datetime) -> bool:
    """The tenant's ENGINE_HOURS capability (master switch; tenant level only)."""
    return PolicyService(s).engine_hours(tenant_id, at=at).policy.enabled


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
        "hours": str(i.explainable_hours),
        "opened_at": i.opened_at.isoformat(),
        "age_days": (now - i.opened_at).days,
    }


def unexplained_dedupe(machine_id: uuid.UUID, start_ref: uuid.UUID, end_ref: uuid.UUID) -> str:
    return f"engine:unexplained:{machine_id}:{start_ref}:{end_ref}"


class EngineHoursMonitor:
    """Machine-level engine-hour flags. Nothing is flagged, aged or reminded while the tenant's ENGINE_HOURS
    capability is switched off."""

    def __init__(self, s: Session, tenant_id: uuid.UUID, now: datetime):
        self._s, self._tid, self._now = s, tenant_id, now

    def enabled(self) -> bool:
        return engine_hours_on(self._s, self._tid, self._now)

    def _flag(
        self,
        machine_id: uuid.UUID,
        kind: ExceptionType,
        dedupe: str,
        evidence: dict[str, Any],
    ) -> bool:
        stamp = PolicyService(self._s).engine_hours(self._tid, machine_id, at=self._now).version_stamp
        new_id = self._s.execute(
            insert(MeterException)
            .values(
                id=uuid.uuid4(),
                tenant_id=self._tid,
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
            .on_conflict_do_nothing(constraint="uq_meter_exception_dedupe")
            .returning(MeterException.id)
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
                    "hours": evidence.get("hours"),
                    "day": evidence.get("day"),
                },
                tenant_id=self._tid,
            )
        return new_id is not None

    def flag_machine(self, machine_id: uuid.UUID) -> int:
        """UNEXPLAINED_HOURS for each verified unexplained segment, once each (dedupe). Only after reconciliation
        began (approved baseline)."""
        machine = self._s.get(Machine, machine_id)
        if machine is None or not self.enabled() or approved_baseline(self._s, machine_id) is None:
            return 0
        ml = load_machine_ledger(self._s, self._tid, machine, self._now)
        raised = 0
        for i in ml.open_items():
            raised += self._flag(
                machine_id,
                ExceptionType.UNEXPLAINED_HOURS,
                unexplained_dedupe(machine_id, i.start.ref, i.end.ref),
                _segment_evidence(i, self._now),
            )
        return raised

    def flag_duplicate_report(self, report: DailyOperationalReport) -> bool:
        """[DEC-032 A6] A second daily operational report for one machine-day: kept and flagged for review."""
        return self._flag(
            report.machine_id,
            ExceptionType.DUPLICATE_DAILY_REPORT,
            f"engine:dup-report:{report.id}",
            {
                "day": report.report_date.isoformat(),
                "report_id": str(report.id),
                "duplicate_of_id": str(report.duplicate_of_id),
            },
        )

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
    basis: str  # ENGINE_ACTIVITY (tracker engine-on in the window)


def missing_daily_reports(s: Session, tenant_id: uuid.UUID, now: datetime) -> list[MissingReport]:
    """Working machines without a reading before the policy cut-off of a tenant-local day whose cut-off has passed
    (today after the cut-off, and yesterday). Working = engine-on reported by its tracker in that window. Per-machine
    policy may switch the requirement off."""
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
        working: set[uuid.UUID] = set()
        engine_on = select(MachineStateEvent.machine_id).where(
            MachineStateEvent.dimension == StateDimension.ENGINE,
            MachineStateEvent.value == "ON",
            MachineStateEvent.event_time >= start,
            MachineStateEvent.event_time < end,
        )
        working.update(s.execute(engine_on.distinct()).scalars())
        if not working:
            continue
        reported = set(
            s.execute(
                select(MeterCapture.machine_id).where(
                    MeterCapture.machine_id.in_(working),
                    MeterCapture.state.in_(LIVE),
                    and_(MeterCapture.captured_at >= start, MeterCapture.captured_at < end),
                )
            ).scalars()
        )
        machines = {m.id: m for m in s.execute(select(Machine).where(Machine.id.in_(working - reported))).scalars()}
        for machine_id, machine in sorted(machines.items(), key=lambda kv: kv[1].asset_code):
            if not svc.engine_hours(tenant_id, machine_id, at=now).policy.daily_report_required:
                continue
            out.append(MissingReport(machine_id, machine.asset_code, machine.name, day, cutoff, "ENGINE_ACTIVITY"))
    return out
