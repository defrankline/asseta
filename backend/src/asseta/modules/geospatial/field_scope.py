"""Which machines a field user may see on the fleet map, machine status and history, and tracking alerts.

People holding a fleet-oversight permission (owner, manager, administrator) see the whole fleet. Everyone else
(supervisors) sees their own machines (assigned to them or on a job they supervise, the same set as "My machines")
unless the tenant's TRACKING.field_fleet_scope is ALL."""

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import Select, false, or_, select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import Machine
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job
from asseta.modules.jobs.scope import assigned_machine_ids, job_filter, own_staff, restricted_to_own
from asseta.modules.policy.schemas import FieldFleetScope
from asseta.modules.policy.service import PolicyService


class HasMachineId(Protocol):
    @property
    def machine_id(self) -> uuid.UUID: ...


FLEET_OVERSIGHT = frozenset(
    {"tenant.machine.read", "tenant.machine.write", "tenant.fleet.alert_manage", "tenant.geofence.write"}
)


def visible_machines(
    session: Session, ctx: RequestContext, tenant_id: uuid.UUID, now: datetime
) -> Select[uuid.UUID] | None:
    """Ids the caller may see, or None when the caller sees the whole fleet."""
    if not restricted_to_own(ctx, FLEET_OVERSIGHT):
        return None
    if PolicyService(session).tracking(tenant_id, at=now).policy.field_fleet_scope == FieldFleetScope.ALL:
        return None
    staff = own_staff(session, ctx)
    if staff is None:
        return select(Machine.id).where(false())
    on_my_jobs = select(Job.machine_id).where(job_filter(staff))
    return select(Machine.id).where(or_(Machine.id.in_(assigned_machine_ids(staff.id)), Machine.id.in_(on_my_jobs)))


def can_see(session: Session, scope: Select[uuid.UUID] | None, machine_id: uuid.UUID | None) -> bool:
    """Alerts without a machine are fleet-wide: only callers who see the whole fleet see them."""
    return scope is None or (machine_id is not None and machine_id in set(session.execute(scope).scalars()))


def only_visible[R: HasMachineId](
    session: Session, ctx: RequestContext, tenant_id: uuid.UUID, now: datetime, rows: list[R]
) -> list[R]:
    """Fleet rows narrowed to what the caller may see (fleet map and the Fleet status report)."""
    scope = visible_machines(session, ctx, tenant_id, now)
    if scope is None:
        return rows
    allowed = set(session.execute(scope).scalars())
    return [r for r in rows if r.machine_id in allowed]
