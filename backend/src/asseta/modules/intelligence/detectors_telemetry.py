"""UNREPORTED_ENGINE_ACTIVITY data loading: verified tracker capabilities, engine states / engine-hour samples and
running jobs per machine, fed to the pure rule. Runs in the tenant's RLS scope."""

import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import AssignmentRole, MachineAssignment
from asseta.modules.intelligence.rules import (
    EngineHoursSample,
    EngineRun,
    EngineState,
    JobWindow,
    SignalFinding,
    runs_from_engine_hours,
    runs_from_states,
    unreported_engine_activity,
)
from asseta.modules.jobs.models import Job
from asseta.modules.policy.service import PolicyService
from asseta.modules.telemetry.models import MachinePositionEvent, MachineStateEvent, StateDimension
from asseta.modules.tracker.models import Capability, TrackerAssignment, TrackerCapability

ENGINE_ON = "ON"


def _verified(s: Session, since: datetime) -> dict[uuid.UUID, dict[Capability, datetime]]:
    """Machines whose (current or recent) tracker has IGNITION / ENGINE_HOURS verified in real data."""
    rows = s.execute(
        select(TrackerAssignment.machine_id, TrackerCapability.capability, func.min(TrackerCapability.verified_at))
        .join(TrackerCapability, TrackerCapability.tracker_id == TrackerAssignment.tracker_id)
        .where(
            TrackerCapability.capability.in_([Capability.IGNITION, Capability.ENGINE_HOURS]),
            TrackerCapability.verified_at.is_not(None),
            or_(TrackerAssignment.effective_to.is_(None), TrackerAssignment.effective_to > since),
        )
        .group_by(TrackerAssignment.machine_id, TrackerCapability.capability)
    ).all()
    out: dict[uuid.UUID, dict[Capability, datetime]] = defaultdict(dict)
    for machine_id, cap, verified_at in rows:
        if verified_at is not None:
            out[machine_id][cap] = verified_at
    return out


def _ignition_runs(s: Session, machine_id: uuid.UUID, since: datetime, now: datetime) -> list[EngineRun]:
    base = select(MachineStateEvent.event_time, MachineStateEvent.value).where(
        MachineStateEvent.machine_id == machine_id, MachineStateEvent.dimension == StateDimension.ENGINE
    )
    prior = s.execute(
        base.where(MachineStateEvent.event_time < since).order_by(MachineStateEvent.event_time.desc()).limit(1)
    ).all()
    rows = s.execute(
        base.where(MachineStateEvent.event_time >= since, MachineStateEvent.event_time <= now).order_by(
            MachineStateEvent.event_time
        )
    ).all()
    return runs_from_states([EngineState(at, value == ENGINE_ON) for at, value in [*prior, *rows]], now)


def _engine_hour_runs(s: Session, machine_id: uuid.UUID, since: datetime, now: datetime) -> list[EngineRun]:
    base = select(MachinePositionEvent.event_time, MachinePositionEvent.engine_hours).where(
        MachinePositionEvent.machine_id == machine_id, MachinePositionEvent.engine_hours.is_not(None)
    )
    prior = s.execute(
        base.where(MachinePositionEvent.event_time < since).order_by(MachinePositionEvent.event_time.desc()).limit(1)
    ).all()
    rows = s.execute(
        base.where(MachinePositionEvent.event_time >= since, MachinePositionEvent.event_time <= now).order_by(
            MachinePositionEvent.event_time
        )
    ).all()
    return runs_from_engine_hours(
        [EngineHoursSample(at, hours) for at, hours in [*prior, *rows] if hours is not None], since
    )


def _job_windows(s: Session, machine_id: uuid.UUID, start: datetime, end: datetime) -> list[JobWindow]:
    rows = s.execute(
        select(Job.id, Job.job_number, Job.started_at, Job.completed_at).where(
            Job.machine_id == machine_id,
            Job.started_at.is_not(None),
            Job.started_at < end,
            or_(Job.completed_at.is_(None), Job.completed_at > start),
        )
    ).all()
    return [JobWindow(jid, number, started, completed) for jid, number, started, completed in rows if started]


def _supervisors(s: Session, machine_id: uuid.UUID, start: datetime, end: datetime) -> list[uuid.UUID]:
    return list(
        s.execute(
            select(MachineAssignment.staff_member_id).where(
                MachineAssignment.machine_id == machine_id,
                MachineAssignment.role == AssignmentRole.SUPERVISOR,
                MachineAssignment.effective_from < end,
                or_(MachineAssignment.effective_to.is_(None), MachineAssignment.effective_to > start),
            )
        ).scalars()
    )


def detect_engine_activity(s: Session, tenant_id: uuid.UUID, now: datetime, since: datetime) -> list[SignalFinding]:
    """Ignition-derived engine states are preferred; engine-hour increases are used only when the machine's tracker
    has ENGINE_HOURS but not IGNITION verified. Machines without a verified capability are never evaluated."""
    findings: list[SignalFinding] = []
    policies = PolicyService(s)
    for machine_id, caps in _verified(s, since).items():
        if Capability.IGNITION in caps:
            verified_since, runs = caps[Capability.IGNITION], _ignition_runs(s, machine_id, since, now)
        else:
            verified_since, runs = caps[Capability.ENGINE_HOURS], _engine_hour_runs(s, machine_id, since, now)
        if not runs:
            continue
        start, end = min(r.start for r in runs), max(r.end for r in runs)
        eff = policies.fraud_controls(tenant_id, machine_id, at=now)
        findings += unreported_engine_activity(
            machine_id,
            runs,
            _job_windows(s, machine_id, start, end),
            verified_since,
            eff.policy.engine_activity_min_minutes,
            eff.version_stamp,
            _supervisors(s, machine_id, start, end),
        )
    return findings
