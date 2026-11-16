"""Where a machine report starts, the tracker cross-check, and the allocation-ledger entries an approval writes.

Previous reading (ADR-008 §2): the end reading of the machine's last APPROVED report, else its approved meter
baseline. An approved meter reset after that point restarts the count at the reset's new reading (the existing reset
flow accounts for the meter change itself)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.modules.machine_reports.models import (
    MachineReport,
    MachineReportLine,
    MachineReportStatus,
    ReportLineKind,
    StartSource,
)
from asseta.modules.meter.allocation_models import AllocationKind, AllocationSource, AllocationStatus, WorkAllocation
from asseta.modules.meter.allocation_writer import tenant_zone
from asseta.modules.meter.engine_models import MachineMeterBaseline, MeterProposalStatus
from asseta.modules.meter.models import MeterCapture, MeterResetEvent

APPROVAL_REF = "machine_report"


@dataclass(frozen=True)
class StartPoint:
    source: StartSource
    ref: uuid.UUID
    reading: Decimal
    at: datetime
    epoch: int


def last_approved(session: Session, machine_id: uuid.UUID) -> MachineReport | None:
    return session.execute(
        select(MachineReport)
        .where(MachineReport.machine_id == machine_id, MachineReport.status == MachineReportStatus.APPROVED)
        .order_by(MachineReport.end_at.desc(), MachineReport.decided_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _epoch(session: Session, machine_id: uuid.UUID, at: datetime) -> int:
    return int(
        session.execute(
            select(func.count()).where(
                MeterResetEvent.machine_id == machine_id,
                MeterResetEvent.status == "APPROVED",
                MeterResetEvent.effective_at <= at,
            )
        ).scalar_one()
    )


def start_point(session: Session, machine_id: uuid.UUID) -> StartPoint | None:
    """The reading a new report on the machine starts from (None: no approved report and no approved baseline)."""
    report = last_approved(session, machine_id)
    point: tuple[StartSource, uuid.UUID, Decimal, datetime] | None = None
    if report is not None:
        point = (StartSource.REPORT, report.id, report.end_reading, report.end_at)
    else:
        baseline = session.execute(
            select(MachineMeterBaseline).where(
                MachineMeterBaseline.machine_id == machine_id,
                MachineMeterBaseline.status == MeterProposalStatus.APPROVED,
            )
        ).scalar_one_or_none()
        if baseline is not None:
            point = (StartSource.BASELINE, baseline.id, baseline.reading, baseline.captured_at)
    if point is None:
        return None
    reset = session.execute(
        select(MeterResetEvent)
        .where(
            MeterResetEvent.machine_id == machine_id,
            MeterResetEvent.status == "APPROVED",
            MeterResetEvent.effective_at > point[3],
        )
        .order_by(MeterResetEvent.effective_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if reset is not None:
        point = (StartSource.RESET, reset.id, reset.new_reading, reset.effective_at)
    return StartPoint(point[0], point[1], point[2], point[3], _epoch(session, machine_id, point[3]))


def tracker_hours(
    session: Session, machine_id: uuid.UUID, start_at: datetime, end_at: datetime
) -> tuple[Decimal, datetime, datetime] | None:
    """Engine hours the machine's tracker counted between two instants (its engine-hour counter at or before each),
    with the counter times used; None when the tracker reports no counter for either end."""
    row = session.execute(
        text("""
        SELECT (SELECT engine_hours FROM machine_position_event WHERE machine_id = :m AND engine_hours IS NOT NULL
                  AND event_time <= :b ORDER BY event_time DESC LIMIT 1),
               (SELECT event_time FROM machine_position_event WHERE machine_id = :m AND engine_hours IS NOT NULL
                  AND event_time <= :b ORDER BY event_time DESC LIMIT 1),
               (SELECT engine_hours FROM machine_position_event WHERE machine_id = :m AND engine_hours IS NOT NULL
                  AND event_time <= :e ORDER BY event_time DESC LIMIT 1),
               (SELECT event_time FROM machine_position_event WHERE machine_id = :m AND engine_hours IS NOT NULL
                  AND event_time <= :e ORDER BY event_time DESC LIMIT 1)"""),
        {"m": machine_id, "b": start_at, "e": end_at},
    ).one()
    if row[0] is None or row[2] is None or row[1] == row[3]:
        return None
    return max(Decimal(row[2]) - Decimal(row[0]), Decimal(0)).quantize(Decimal("0.01")), row[1], row[3]


def write_allocations(
    session: Session,
    actor: AuditActor,
    report: MachineReport,
    lines: list[MachineReportLine],
    lots: dict[uuid.UUID, list[dict[str, Any]]],
) -> list[WorkAllocation]:
    """The approved split in the allocation ledger: one entry per line, laid end to end over the report's meter range
    in line order (customer work with its lots; non-productive hours as authorised activity with the reason). Entries
    other writers hold over that range are superseded: the approved report is the account of those hours."""
    assert report.decided_at is not None
    overlapping = session.execute(
        select(WorkAllocation)
        .where(
            WorkAllocation.machine_id == report.machine_id,
            WorkAllocation.meter_epoch == report.meter_epoch,
            WorkAllocation.status == AllocationStatus.ACTIVE,
            WorkAllocation.start_reading < report.end_reading,
            WorkAllocation.end_reading > report.start_reading,
        )
        .with_for_update()
    ).scalars()
    for row in overlapping:
        row.status, row.superseded_at = AllocationStatus.SUPERSEDED, report.decided_at
    session.flush()  # the old ranges leave the exclusion constraint before the report's enter it
    photo = session.execute(
        select(MeterCapture.photo_attachment_id).where(MeterCapture.id == report.capture_id)
    ).scalar_one_or_none()
    work_date = report.end_at.astimezone(tenant_zone(session, report.tenant_id)).date()
    at = report.start_reading
    out = []
    for line in sorted(lines, key=lambda x: x.line_no):
        customer = line.kind is ReportLineKind.CUSTOMER
        row = WorkAllocation(
            id=uuid.uuid4(),
            tenant_id=report.tenant_id,
            machine_id=report.machine_id,
            work_date=work_date,
            start_ref=report.start_ref,
            start_reading=at,
            start_at=report.start_at,
            end_ref=report.capture_id,
            end_reading=at + line.hours,
            end_at=report.end_at,
            meter_epoch=report.meter_epoch,
            hours=line.hours,
            kind=AllocationKind.CUSTOMER_WORK if customer else AllocationKind.AUTHORIZED_ACTIVITY,
            customer_id=line.customer_id,
            reason_id=line.reason_id,
            reading_review="VERIFIED",
            approval_ref_type=APPROVAL_REF,
            approval_ref_ids=[report.id],
            lots=lots.get(line.id, []),
            evidence_attachment_ids=[photo] if photo else [],
            source=AllocationSource.MACHINE_REPORT,
            status=AllocationStatus.ACTIVE,
            origin_key=f"mr:{report.id}:{line.line_no}",
            origin_hours=line.hours,
            recorded_by=report.submitted_by,
            decided_by=report.decided_by,
            decided_at=report.decided_at,
            policy_version=report.policy_version[:80],
            created_at=report.decided_at,
        )
        session.add(row)
        at += line.hours
        out.append(row)
    session.flush()
    for row in out:
        AuditService(session).record(
            actor=actor,
            action="meter.work_allocation.posted",
            entity_type="work_allocation",
            entity_id=row.id,
            tenant_id=report.tenant_id,
            after={
                "machine_id": str(row.machine_id),
                "work_date": row.work_date.isoformat(),
                "kind": row.kind.value,
                "hours": str(row.hours),
                "machine_report_id": str(report.id),
            },
        )
    return out
