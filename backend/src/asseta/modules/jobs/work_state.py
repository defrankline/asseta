"""Reported work state per machine, from supervisor reports only (jobs + work logs) — never inferred from GPS or
engine data, which are separate observed dimensions on the fleet map.

    WORK / STANDBY / DOWNTIME / MOBILIZATION   the open (not yet ended) work-log activity of the machine's
                                               IN_PROGRESS job, latest started first
    ON_JOB                                     an IN_PROGRESS job with no open activity logged
    NO_ACTIVE_JOB                              no job in progress for the machine
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.jobs.models import ActivityType, Job, JobActivity, JobStatus


class ReportedWorkState(StrEnum):
    WORK = "WORK"
    STANDBY = "STANDBY"
    DOWNTIME = "DOWNTIME"
    MOBILIZATION = "MOBILIZATION"
    ON_JOB = "ON_JOB"
    NO_ACTIVE_JOB = "NO_ACTIVE_JOB"


_FROM_ACTIVITY = {
    ActivityType.WORK: ReportedWorkState.WORK,
    ActivityType.STANDBY: ReportedWorkState.STANDBY,
    ActivityType.DOWNTIME: ReportedWorkState.DOWNTIME,
    ActivityType.MOBILIZATION: ReportedWorkState.MOBILIZATION,
}


def reported_work_states(session: Session, now: datetime) -> dict[uuid.UUID, ReportedWorkState]:
    """Machines with a job in progress -> their reported state (RLS-scoped to the caller's tenant). Machines that
    are absent have no active job (`NO_ACTIVE_JOB`)."""
    active = dict(
        session.execute(select(Job.machine_id, Job.id).where(Job.status == JobStatus.IN_PROGRESS)).tuples().all()
    )
    if not active:
        return {}
    states = dict.fromkeys(active, ReportedWorkState.ON_JOB)
    by_job = {job_id: machine_id for machine_id, job_id in active.items()}
    rows = session.execute(
        select(JobActivity.job_id, JobActivity.activity_type)
        .where(
            JobActivity.job_id.in_(by_job),
            JobActivity.started_at <= now,
            JobActivity.ended_at.is_(None),
            JobActivity.activity_type.in_(_FROM_ACTIVITY),
        )
        .order_by(JobActivity.started_at)
    ).tuples()
    for job_id, activity in rows:  # ascending: the latest started open activity wins
        states[by_job[job_id]] = _FROM_ACTIVITY[activity]
    return states
