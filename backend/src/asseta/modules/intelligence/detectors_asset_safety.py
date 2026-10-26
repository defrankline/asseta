"""DEC-031 Phase 2 (asset safety) data loading: engine running without work per machine-day (S1) and fuel against
engine hours per machine-period (S2). Only closed tenant-local days / periods inside the sweep lookback are
evaluated, so each summary sees the whole period; dedupe keys make re-runs no-ops. Runs in the tenant's RLS scope.
Both rules are FRAUD_CONTROLS thresholds that are off (None) by default."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import FuelEvent, FuelEventType
from asseta.modules.finance.common import tenant_settings
from asseta.modules.fleet.models import Machine
from asseta.modules.geospatial.models import AlertStatus, AlertType, TrackingAlert
from asseta.modules.intelligence.detectors_telemetry import (
    _engine_hour_runs,
    _ignition_runs,
    _job_windows,
    _supervisors,
    _verified,
)
from asseta.modules.intelligence.models import RiskSignal, RuleCode
from asseta.modules.intelligence.rules import (
    EngineDay,
    MachineFuelPeriod,
    MeterGap,
    MovementAlert,
    SignalFinding,
    TrackerGap,
    engine_running_without_work,
    machine_fuel_above_norm,
    uncovered,
)
from asseta.modules.meter.engine_hours import EngineHoursMonitor, MachineLedger, load_machine_ledger
from asseta.modules.meter.ledger import SegmentClassification, SegmentKind
from asseta.modules.policy.schemas import FraudControlsPolicy, FuelCheckPeriod, PolicyScope, PolicyType
from asseta.modules.policy.service import EffectivePolicy, PolicyService
from asseta.modules.revenue.compute import overlap_fraction
from asseta.modules.tracker.models import Capability

FUEL_INTO_MACHINE = (FuelEventType.ISSUE, FuelEventType.PURCHASE)
NORM_KEY = "fuel_litres_per_hour_max"
NORM_SOURCES = {
    PolicyScope.MACHINE: "MACHINE",
    PolicyScope.MACHINE_CATEGORY: "MACHINE_CATEGORY",
    PolicyScope.TENANT: "TENANT",
    PolicyScope.PLATFORM: "PLATFORM",
}
Period = tuple[str, datetime, datetime]  # key, UTC start, UTC end


def _closed_days(tz: ZoneInfo, since: datetime, now: datetime) -> list[tuple[date, datetime, datetime]]:
    """Tenant-local days that have ended by `now` and end after `since`."""
    day = since.astimezone(tz).date()
    out: list[tuple[date, datetime, datetime]] = []
    while True:
        start = datetime.combine(day, time.min, tz).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time.min, tz).astimezone(UTC)
        if end > now:
            return out
        if end > since:
            out.append((day, start, end))
        day += timedelta(days=1)


def _closed_periods(kind: FuelCheckPeriod, tz: ZoneInfo, since: datetime, now: datetime) -> list[Period]:
    if kind is FuelCheckPeriod.DAY:
        return [(d.isoformat(), a, b) for d, a, b in _closed_days(tz, since, now)]
    first = since.astimezone(tz).date()
    monday = first - timedelta(days=first.weekday())
    out: list[Period] = []
    while True:
        start = datetime.combine(monday, time.min, tz).astimezone(UTC)
        end = datetime.combine(monday + timedelta(days=7), time.min, tz).astimezone(UTC)
        if end > now:
            return out
        if end > since:
            iso = monday.isocalendar()
            out.append((f"{iso.year}-W{iso.week:02d}", start, end))
        monday += timedelta(days=7)


# --- S1: engine running without work ---------------------------------------------------------------------------
def _tracker_gaps(
    s: Session, machine_id: uuid.UUID, caps: dict[Capability, datetime], start: datetime, end: datetime
) -> list[TrackerGap]:
    """Verified engine-on time with no running job in [start, end) (any length; the per-signal minimum of
    UNREPORTED_ENGINE_ACTIVITY does not apply to the day total)."""
    if Capability.IGNITION in caps:
        verified_since, runs = caps[Capability.IGNITION], _ignition_runs(s, machine_id, start, end)
    else:
        verified_since, runs = caps[Capability.ENGINE_HOURS], _engine_hour_runs(s, machine_id, start, end)
    if not runs:
        return []
    jobs = _job_windows(s, machine_id, min(r.start for r in runs), max(r.end for r in runs))
    gaps = []
    for run in runs:
        lo, hi = max(run.start, verified_since, start), min(run.end, end)
        if lo >= hi:
            continue
        gaps += [TrackerGap(a, b, str(run.detail.get("basis", ""))) for a, b in uncovered(lo, hi, jobs)]
    return gaps


def _meter_gaps(ml: MachineLedger, start: datetime, end: datetime) -> list[MeterGap]:
    """Unexplained engine hours outside jobs (reconciled machines only, like the engine-hour flags)."""
    if not ml.reconciling:
        return []
    out = []
    for i in ml.ledger.intervals:
        if i.kind is not SegmentKind.UNALLOCATED or i.classification is not SegmentClassification.UNEXPLAINED:
            continue
        share = i.hours * overlap_fraction(i.start.at, i.end.at, start, end)
        if share > 0:
            out.append(
                MeterGap(i.start.ref, i.end.ref, i.start.at, i.end.at, i.start.reading, i.end.reading, i.hours, share)
            )
    return out


def _movements(
    s: Session, machine_ids: Iterable[uuid.UUID], start: datetime, end: datetime
) -> dict[uuid.UUID, list[MovementAlert]]:
    out: dict[uuid.UUID, list[MovementAlert]] = defaultdict(list)
    for a in s.execute(
        select(TrackingAlert)
        .where(
            TrackingAlert.machine_id.in_(list(machine_ids)),
            TrackingAlert.alert_type == AlertType.UNAUTHORIZED_MOVEMENT,
            TrackingAlert.status != AlertStatus.SUPERSEDED,
            TrackingAlert.event_time >= start,
            TrackingAlert.event_time < end,
        )
        .order_by(TrackingAlert.event_time)
    ).scalars():
        assert a.machine_id is not None
        out[a.machine_id].append(MovementAlert(a.id, a.event_time, a.title))
    return out


def detect_engine_without_work(s: Session, tenant_id: uuid.UUID, now: datetime, since: datetime) -> list[SignalFinding]:
    """One ENGINE_RUNNING_WITHOUT_WORK summary per machine and closed tenant-local day whose engine time without
    work reaches the machine's `engine_without_work_case_min_minutes`."""
    days = _closed_days(ZoneInfo(tenant_settings(s, tenant_id).timezone), since, now)
    if not days:
        return []
    start, end = days[0][1], days[-1][2]
    policies = PolicyService(s)
    trackers = _verified(s, start)
    baselined = {m.id: m for m in EngineHoursMonitor(s, tenant_id, now).baselined_machines()}
    candidates = set(trackers) | set(baselined)
    movers = _movements(s, candidates, start, end) if candidates else {}
    findings: list[SignalFinding] = []
    for machine_id in sorted(candidates, key=str):
        eff = policies.fraud_controls(tenant_id, machine_id, at=now)
        min_minutes = eff.policy.engine_without_work_case_min_minutes
        if min_minutes is None:
            continue
        tracker = _tracker_gaps(s, machine_id, trackers[machine_id], start, end) if machine_id in trackers else []
        machine = baselined.get(machine_id)
        ml = load_machine_ledger(s, tenant_id, machine, now) if machine is not None else None
        related = list(
            s.execute(
                select(RiskSignal.id, RiskSignal.window_start).where(
                    RiskSignal.machine_id == machine_id,
                    RiskSignal.rule_code == RuleCode.UNREPORTED_ENGINE_ACTIVITY,
                    RiskSignal.window_start >= start,
                    RiskSignal.window_start < end,
                )
            ).all()
        )
        supervisors = tuple(_supervisors(s, machine_id, start, end))
        for day, d0, d1 in days:
            day_tracker = tuple(
                TrackerGap(max(g.start, d0), min(g.end, d1), g.basis) for g in tracker if g.start < d1 and g.end > d0
            )
            day_meter = tuple(_meter_gaps(ml, d0, d1)) if ml is not None else ()
            summary = EngineDay(
                machine_id,
                day,
                d0,
                d1,
                day_tracker,
                day_meter,
                tuple(m for m in movers.get(machine_id, []) if d0 <= m.at < d1),
                tuple(sid for sid, at in related if d0 <= at < d1),
                supervisors,
            )
            if finding := engine_running_without_work(summary, min_minutes, eff.version_stamp):
                findings.append(finding)
    return findings


# --- S2: fuel against engine hours per machine -----------------------------------------------------------------
def _norm(
    policies: PolicyService, tenant_id: uuid.UUID, machine_id: uuid.UUID, at: datetime
) -> tuple[EffectivePolicy[FraudControlsPolicy], str]:
    """The machine's effective norm and where it is set (machine > machine category > tenant)."""
    eff = policies.fraud_controls(tenant_id, machine_id, at=at)
    source = policies.value_source(PolicyType.FRAUD_CONTROLS, NORM_KEY, tenant_id, machine_id=machine_id, at=at)
    return eff, NORM_SOURCES.get(source, "TENANT") if source is not None else "TENANT"


def detect_machine_fuel(s: Session, tenant_id: uuid.UUID, now: datetime, since: datetime) -> list[SignalFinding]:
    """Per machine and closed tenant-local period (`fuel_check_period`): litres issued or purchased into the machine
    vs its engine hours from the meter ledger (inside and outside jobs, split by wall-clock time). A period is
    judged only when the machine's readings cover it from start to end."""
    tenant_eff = PolicyService(s).fraud_controls(tenant_id, at=now)
    kind = tenant_eff.policy.fuel_check_period
    if kind is None:
        return []
    periods = _closed_periods(kind, ZoneInfo(tenant_settings(s, tenant_id).timezone), since, now)
    if not periods:
        return []
    start, end = periods[0][1], periods[-1][2]
    by_machine: dict[uuid.UUID, list[FuelEvent]] = defaultdict(list)
    for f in s.execute(
        select(FuelEvent).where(
            FuelEvent.machine_id.is_not(None),
            FuelEvent.event_type.in_(FUEL_INTO_MACHINE),
            FuelEvent.occurred_at >= start,
            FuelEvent.occurred_at < end,
        )
    ).scalars():
        assert f.machine_id is not None
        by_machine[f.machine_id].append(f)
    policies, findings = PolicyService(s), []
    for machine_id, fuel in sorted(by_machine.items(), key=lambda kv: str(kv[0])):
        eff, source = _norm(policies, tenant_id, machine_id, now)
        norm = eff.policy.fuel_litres_per_hour_max
        machine = s.get(Machine, machine_id)
        if norm is None or machine is None:
            continue
        intervals = load_machine_ledger(s, tenant_id, machine, now).ledger.intervals
        if not intervals:
            continue
        first, last = min(i.start.at for i in intervals), max(i.end.at for i in intervals)
        for key, p0, p1 in periods:
            events = [f for f in fuel if p0 <= f.occurred_at < p1]
            if not events or first > p0 or last < p1:
                continue  # no fuel, or engine hours not known for the whole period
            hours = in_jobs = Decimal(0)
            jobs: set[str] = set()
            for i in intervals:
                share = i.hours * overlap_fraction(i.start.at, i.end.at, p0, p1)
                if share <= 0:
                    continue
                hours += share
                if i.kind is SegmentKind.CUSTOMER_WORK:
                    in_jobs += share
                    if i.job_number:
                        jobs.add(i.job_number)
            period = MachineFuelPeriod(
                machine_id,
                kind.value,
                key,
                p0,
                p1,
                sum((f.litres for f in events), Decimal(0)),
                hours,
                in_jobs,
                tuple(f.id for f in events),
                tuple(f.recorded_by for f in events if f.recorded_by),
                tuple(sorted(jobs)),
            )
            if finding := machine_fuel_above_norm(period, norm, source, eff.version_stamp):
                findings.append(finding)
    return findings
