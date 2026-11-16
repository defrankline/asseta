"""Idle machines (DEC-031 M2, re-pointed by ADR-008): active machines with no approved machine-report hours for at
least OVERSIGHT.idle_after_days. Read model over approved machine reports (and, for information, tracker engine-on
states). Off while idle_after_days is null."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.search import ilike_any
from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.machine_reports.models import MachineReport, MachineReportStatus
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
    last_report: dict[uuid.UUID, tuple[uuid.UUID, datetime]] = {
        machine_id: (report_id, end_at)
        for machine_id, report_id, end_at in s.execute(
            select(MachineReport.machine_id, MachineReport.id, MachineReport.end_at)
            .distinct(MachineReport.machine_id)
            .where(
                MachineReport.machine_id.in_(ids),
                MachineReport.status == MachineReportStatus.APPROVED,
                MachineReport.hours > 0,
            )
            .order_by(MachineReport.machine_id, MachineReport.end_at.desc())
        ).tuples()
    }
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
        report = last_report.get(m.id)
        since = max(m.created_at, report[1]) if report else m.created_at
        if now - since < timedelta(days=after):
            continue
        out.append(
            IdleMachineDto(
                machine_id=m.id,
                category_id=m.category_id,
                idle_since=since,
                idle_days=(now - since).days,
                last_machine_report_id=report[0] if report else None,
                last_engine_activity_at=engine_at.get(m.id),
            )
        )
    out.sort(key=lambda r: (r.idle_since, str(r.machine_id)))
    return out
