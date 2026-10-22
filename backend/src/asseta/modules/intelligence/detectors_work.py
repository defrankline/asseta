"""WORK_WITHOUT_AUTHORIZATION data loading: job activities, meter readings and expenses received since `since`,
with the job's authorization period and the recorder's supervisor assignment at the time (see the rule docstring
for what the domain already refuses)."""

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import Expense, ExpenseStatus
from asseta.modules.fleet.models import AssignmentRole, MachineAssignment, StaffKind, StaffMember
from asseta.modules.identity.models import AppUser
from asseta.modules.intelligence.rules import SignalFinding, WorkRecord, work_without_authorization
from asseta.modules.jobs.models import Job, JobActivity
from asseta.modules.meter.models import CaptureState, MeterCapture
from asseta.modules.policy.schemas import FraudControlsPolicy
from asseta.modules.policy.service import EffectivePolicy

Raw = tuple[str, uuid.UUID, Job, datetime, datetime, uuid.UUID | None]


def _raw_records(s: Session, since: datetime, expense_ids: set[uuid.UUID] | None) -> list[Raw]:
    out: list[Raw] = []
    if expense_ids is None:
        for a, job in s.execute(
            select(JobActivity, Job).join(Job, Job.id == JobActivity.job_id).where(JobActivity.received_at >= since)
        ).all():
            out.append(("JOB_ACTIVITY", a.id, job, a.started_at, a.received_at, a.recorded_by))
        for c, job in s.execute(
            select(MeterCapture, Job)
            .join(Job, Job.id == MeterCapture.job_id)
            .where(MeterCapture.received_at >= since, MeterCapture.state != CaptureState.REJECTED)
        ).all():
            out.append(("METER_CAPTURE", c.id, job, c.captured_at, c.received_at, c.supervisor_user_id))
    stmt = select(Expense, Job).join(Job, Job.id == Expense.job_id).where(Expense.status != ExpenseStatus.REJECTED)
    stmt = (
        stmt.where(Expense.id.in_(expense_ids))
        if expense_ids is not None
        else stmt.where(Expense.submitted_at >= since)
    )
    for e, job in s.execute(stmt).all():
        out.append(("EXPENSE", e.id, job, e.incurred_at, e.submitted_at, e.submitted_by))
    return out


def _supervisor_staff(s: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    """user id -> supervisor staff id, for recorders whose login is linked to a SUPERVISOR staff record."""
    if not user_ids:
        return {}
    rows = s.execute(
        select(AppUser.id, StaffMember.id)
        .join(StaffMember, StaffMember.keycloak_subject == AppUser.keycloak_subject)
        .where(AppUser.id.in_(user_ids), StaffMember.kind == StaffKind.SUPERVISOR)
    ).all()
    return dict(rows)


def _assigned(s: Session, machine_id: uuid.UUID, staff_id: uuid.UUID, at: datetime) -> bool:
    return (
        s.execute(
            select(MachineAssignment.id)
            .where(
                MachineAssignment.machine_id == machine_id,
                MachineAssignment.staff_member_id == staff_id,
                MachineAssignment.role == AssignmentRole.SUPERVISOR,
                MachineAssignment.effective_from <= at,
                or_(MachineAssignment.effective_to.is_(None), MachineAssignment.effective_to > at),
            )
            .limit(1)
        ).first()
        is not None
    )


def detect_work_without_authorization(
    s: Session,
    eff: EffectivePolicy[FraudControlsPolicy],
    since: datetime,
    expense_ids: set[uuid.UUID] | None = None,
) -> list[SignalFinding]:
    raw = _raw_records(s, since, expense_ids)
    staff = _supervisor_staff(s, {r[5] for r in raw if r[5] is not None})
    out = []
    for kind, record_id, job, occurred_at, received_at, user_id in raw:
        staff_id = staff.get(user_id) if user_id is not None else None
        rec = WorkRecord(
            kind,
            record_id,
            job.id,
            job.job_number,
            job.machine_id,
            occurred_at,
            received_at,
            job.status.value,
            job.approved_at,
            job.completed_at,
            user_id,
            staff_id,
            _assigned(s, job.machine_id, staff_id, occurred_at) if staff_id is not None else None,
        )
        if f := work_without_authorization(rec, eff.policy.authorization_tolerance_minutes, eff.version_stamp):
            out.append(f)
    return out
