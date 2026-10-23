"""Least-privilege "own records" scoping for field users (supervisors).

A caller who holds none of the office/oversight permissions for a domain sees only their own field records (or
records of the jobs/machines they supervise); office roles see the whole tenant unless they ask for `mine=true`.
RLS still bounds everything to the tenant; this narrows within it."""

import uuid
from typing import Any

from sqlalchemy import Select, false, or_, select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import MachineAssignment, StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job

# Holding any of these means the caller oversees the domain tenant-wide (owner, manager, accountant).
EXPENSE_OVERSIGHT = frozenset(
    {
        "tenant.approval.read",
        "tenant.approval.expense",
        "tenant.finance.report",
        "tenant.finance.cash",
        "tenant.finance.verify",
        "tenant.finance.expense_category",
    }
)
METER_OVERSIGHT = frozenset(
    {"tenant.meter.review", "tenant.meter.approve", "tenant.job.write", "tenant.job.approve", "tenant.finance.report"}
)


def restricted_to_own(ctx: RequestContext, oversight: frozenset[str], mine: bool = False) -> bool:
    """True when the caller must only see their own records (explicit `mine` or no oversight permission)."""
    return mine or not (oversight & set(ctx.permissions))


def own_staff(session: Session, ctx: RequestContext) -> StaffMember | None:
    """The caller's active linked staff record (None when the login is not linked)."""
    return session.execute(
        select(StaffMember).where(StaffMember.keycloak_subject == ctx.subject, StaffMember.is_active.is_(True))
    ).scalar_one_or_none()


def assigned_machine_ids(staff_id: uuid.UUID) -> Select[uuid.UUID]:
    """Machines the staff member is currently assigned to (open assignments)."""
    return select(MachineAssignment.machine_id).where(
        MachineAssignment.staff_member_id == staff_id, MachineAssignment.effective_to.is_(None)
    )


def job_filter(staff: StaffMember | None) -> Any:
    """Jobs a supervisor is responsible for: named supervisor, or on a machine currently assigned to them."""
    if staff is None:
        return false()  # no linked staff record: nothing assigned
    return or_(Job.supervisor_id == staff.id, Job.machine_id.in_(assigned_machine_ids(staff.id)))


def scoped_job_ids(staff: StaffMember | None) -> Select[uuid.UUID]:
    return select(Job.id).where(job_filter(staff))
