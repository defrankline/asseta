"""Idle machines (DEC-031 M2): active machines with no running job and no engine hours for at least
OVERSIGHT.idle_after_days. Read model over jobs, live meter readings (a reading above the previous one = engine
hours) and tracker engine-on states. Off while idle_after_days is null."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.search import ilike_any
from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.meter.engine_hours import LIVE
from asseta.modules.meter.models import MeterCapture
from asseta.modules.oversight.dto import IdleMachineDto
from asseta.modules.policy.service import PolicyService
from asseta.modules.telemetry.models import MachineStateEvent, StateDimension


def idle_machines(
    s: Session,
    tenant_id: uuid.UUID,
    now: datetime,
    *,
    q: str | None = None,
    category_id: uuid.UUID | None = None,
) -> list[IdleMachineDto]:
    """Longest idle first. Empty while the check is off."""
    after = PolicyService(s).oversight(tenant_id, at=now).policy.idle_after_days
    if after is None:
        return []
    stmt = select(Machine).where(Machine.deactivated_at.is_(None), Machine.status == MachineStatus.ACTIVE)
    if category_id:
        stmt = stmt.where(Machine.category_id == category_id)
    if (cond := ilike_any(q, Machine.asset_code, Machine.name)) is not None:
        stmt = stmt.where(cond)
    machines = list(s.execute(stmt).scalars())
    if not machines:
        return []
    ids = [m.id for m in machines]
    running = set(
        s.execute(select(Job.machine_id).where(Job.status == JobStatus.IN_PROGRESS, Job.machine_id.in_(ids))).scalars()
    )
    last_job: dict[uuid.UUID, tuple[uuid.UUID, datetime | None]] = {}
    for job_id, machine_id, completed in s.execute(
        select(Job.id, Job.machine_id, Job.completed_at)
        .where(Job.status == JobStatus.COMPLETED, Job.machine_id.in_(ids))
        .order_by(Job.machine_id, Job.completed_at.desc())
    ).all():
        last_job.setdefault(machine_id, (job_id, completed))
    planned = {
        m: j
        for j, m in s.execute(
            select(Job.id, Job.machine_id).where(Job.status == JobStatus.APPROVED, Job.machine_id.in_(ids))
        ).all()
    }
    readings = (
        select(
            MeterCapture.machine_id,
            MeterCapture.captured_at,
            MeterCapture.reading,
            func.lag(MeterCapture.reading)
            .over(partition_by=MeterCapture.machine_id, order_by=MeterCapture.captured_at)
            .label("previous"),
        )
        .where(MeterCapture.state.in_(LIVE), MeterCapture.machine_id.in_(ids))
        .subquery()
    )
    meter_at = dict(
        s.execute(
            select(readings.c.machine_id, func.max(readings.c.captured_at))
            .where(readings.c.reading > readings.c.previous)
            .group_by(readings.c.machine_id)
        ).all()
    )
    engine_at = dict(
        s.execute(
            select(MachineStateEvent.machine_id, func.max(MachineStateEvent.event_time))
            .where(
                MachineStateEvent.machine_id.in_(ids),
                MachineStateEvent.dimension == StateDimension.ENGINE,
                MachineStateEvent.value == "ON",
            )
            .group_by(MachineStateEvent.machine_id)
        ).all()
    )
    out = []
    for m in machines:
        if m.id in running:
            continue
        job = last_job.get(m.id)
        engine = max((t for t in (meter_at.get(m.id), engine_at.get(m.id)) if t is not None), default=None)
        since = max(t for t in (m.created_at, job[1] if job else None, engine) if t is not None)
        if now - since < timedelta(days=after):
            continue
        out.append(
            IdleMachineDto(
                machine_id=m.id,
                category_id=m.category_id,
                idle_since=since,
                idle_days=(now - since).days,
                last_job_id=job[0] if job else None,
                last_job_completed_at=job[1] if job else None,
                last_engine_activity_at=engine,
                planned_job_id=planned.get(m.id),
            )
        )
    out.sort(key=lambda r: (r.idle_since, str(r.machine_id)))
    return out
