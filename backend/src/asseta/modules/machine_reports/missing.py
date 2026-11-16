"""Machines that moved without a machine report (ADR-008 §2 reminder, CUSTOMER_HOURS.machine_report_reminder_days).

A machine qualifies when it has had no report (any status) for the tenant's number of days and, since its last report
(within a 30-day look-back), a meter reading went above its last approved reading or its tracker reported the engine on
or the machine moving. A machine that stood still needs no report. Evidence for a reminder, never a verdict."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.hours.engine import hours_policy
from asseta.modules.machine_reports.models import MachineReport
from asseta.modules.machine_reports.readings import start_point
from asseta.modules.meter.models import CaptureState, MeterCapture

LOOKBACK = timedelta(days=30)


@dataclass(frozen=True)
class MissingReport:
    machine_id: uuid.UUID
    machine_code: str
    machine_name: str
    days: int
    basis: str  # "meter reading" | "tracker activity"


def machines_without_reports(session: Session, tenant_id: uuid.UUID, now: datetime) -> list[MissingReport]:
    days = hours_policy(session, tenant_id, now).policy.machine_report_reminder_days
    if days is None:
        return []
    since = now - timedelta(days=days)
    reported = dict(
        session.execute(
            select(MachineReport.machine_id, func.max(MachineReport.submitted_at)).group_by(MachineReport.machine_id)
        ).all()
    )
    out = []
    for machine in session.execute(
        select(Machine).where(Machine.status != MachineStatus.DISPOSED).order_by(Machine.asset_code)
    ).scalars():
        last = reported.get(machine.id)
        if last is not None and last >= since:
            continue
        # Movement nobody has reported on yet: since the last report, within a bounded look-back.
        after = max(last, now - LOOKBACK) if last is not None else now - LOOKBACK
        basis = None
        point = start_point(session, machine.id)
        moved = select(MeterCapture.id).where(
            MeterCapture.machine_id == machine.id,
            MeterCapture.captured_at > after,
            MeterCapture.state.in_((CaptureState.ACCEPTED, CaptureState.PROVISIONAL)),
        )
        if point is not None:
            moved = moved.where(MeterCapture.reading > point.reading)
        if session.execute(moved.limit(1)).first() is not None:
            basis = "meter reading"
        elif session.execute(
            text(
                "SELECT 1 FROM machine_position_event WHERE machine_id = :m AND event_time > :s "
                "AND (ignition IS TRUE OR motion IS TRUE) LIMIT 1"
            ),
            {"m": machine.id, "s": after},
        ).first():
            basis = "tracker activity"
        if basis is None:
            continue
        out.append(
            MissingReport(
                machine.id,
                machine.asset_code,
                machine.name,
                (now - last).days if last is not None else days,
                basis,
            )
        )
    return out
