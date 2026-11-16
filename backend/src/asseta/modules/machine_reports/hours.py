"""Customer hours for machine reports (ADR-008 §2): what a report may draw on and the FIFO consumption on approval.

Available hours of a customer = activated hours not yet used (the hours ledger, orders not cancelled) minus the hours
other SUBMITTED reports reserve. CUSTOMER_HOURS.report_hours_scope decides whose hours count: CUSTOMER (any of the
customer's hours, whichever machine the order named) or MACHINE (only the customer's hours on the reported machine).
On approval the hours are consumed from the customer's orders oldest activated first (FIFO), one CONSUMED entry per
order lot, each on the machine the lot's hours are on, linked to the report."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.modules.hours.engine import HoursEngine
from asseta.modules.hours.ledger import ZERO, purchase_totals
from asseta.modules.hours.models import SIGN, HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.machine_reports.models import (
    MachineReport,
    MachineReportLine,
    MachineReportStatus,
    ReportLineKind,
)
from asseta.modules.policy.schemas import ReportHoursScope


@dataclass(frozen=True)
class Available:
    customer_id: uuid.UUID
    remaining: Decimal
    reserved: Decimal

    @property
    def available(self) -> Decimal:
        return self.remaining - self.reserved


def scoped_machine(scope: ReportHoursScope, machine_id: uuid.UUID) -> uuid.UUID | None:
    """The machine whose hours count, or None when any of the customer's hours do."""
    return machine_id if scope is ReportHoursScope.MACHINE else None


def remaining_hours(
    session: Session, customer_ids: Iterable[uuid.UUID] | None, machine_id: uuid.UUID | None
) -> dict[uuid.UUID, Decimal]:
    """Activated hours not yet used per customer (orders not cancelled), on one machine or on all of them."""
    stmt = (
        select(HoursLedgerEntry.customer_id, HoursLedgerEntry.entry_type, func.sum(HoursLedgerEntry.hours))
        .join(HoursPurchase, HoursPurchase.id == HoursLedgerEntry.purchase_id)
        .where(HoursPurchase.cancelled_at.is_(None))
        .group_by(HoursLedgerEntry.customer_id, HoursLedgerEntry.entry_type)
    )
    if customer_ids is not None:
        stmt = stmt.where(HoursLedgerEntry.customer_id.in_(list(customer_ids)))
    if machine_id is not None:
        stmt = stmt.where(HoursLedgerEntry.machine_id == machine_id)
    out: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for cid, entry_type, hours in session.execute(stmt):
        out[cid] += SIGN[entry_type] * Decimal(hours)
    return dict(out)


def reserved_hours(
    session: Session,
    customer_ids: Iterable[uuid.UUID] | None,
    machine_id: uuid.UUID | None,
    exclude_report_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, Decimal]:
    """Customer hours held by SUBMITTED reports (on one machine, or on every machine)."""
    stmt = (
        select(MachineReportLine.customer_id, func.sum(MachineReportLine.hours))
        .join(MachineReport, MachineReport.id == MachineReportLine.report_id)
        .where(MachineReport.status == MachineReportStatus.SUBMITTED, MachineReportLine.kind == ReportLineKind.CUSTOMER)
        .group_by(MachineReportLine.customer_id)
    )
    if customer_ids is not None:
        stmt = stmt.where(MachineReportLine.customer_id.in_(list(customer_ids)))
    if machine_id is not None:
        stmt = stmt.where(MachineReport.machine_id == machine_id)
    if exclude_report_id is not None:
        stmt = stmt.where(MachineReport.id != exclude_report_id)
    return {cid: Decimal(h) for cid, h in session.execute(stmt) if cid is not None}


def available_hours(
    session: Session,
    customer_ids: Iterable[uuid.UUID] | None,
    machine_id: uuid.UUID | None,
    exclude_report_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, Available]:
    ids = list(customer_ids) if customer_ids is not None else None
    remaining = remaining_hours(session, ids, machine_id)
    reserved = reserved_hours(session, ids, machine_id, exclude_report_id)
    wanted = ids if ids is not None else sorted({*remaining, *reserved}, key=str)
    return {
        cid: Available(cid, remaining.get(cid, ZERO), reserved.get(cid, ZERO))
        for cid in wanted
        if ids is not None or remaining.get(cid, ZERO) > 0 or reserved.get(cid, ZERO) > 0
    }


def _fifo_purchases(session: Session, customer_id: uuid.UUID) -> list[HoursPurchase]:
    """The customer's open orders, locked, oldest activated first (FIFO)."""
    first_activated = (
        select(func.min(HoursLedgerEntry.occurred_at))
        .where(
            HoursLedgerEntry.purchase_id == HoursPurchase.id,
            HoursLedgerEntry.entry_type == LedgerEntryType.ACTIVATED,
        )
        .scalar_subquery()
    )
    return list(
        session.execute(
            select(HoursPurchase)
            .where(HoursPurchase.customer_id == customer_id, HoursPurchase.cancelled_at.is_(None))
            .order_by(first_activated.asc().nulls_last(), HoursPurchase.created_at, HoursPurchase.purchase_number)
            .with_for_update()
        ).scalars()
    )


def consume(
    engine: HoursEngine,
    session: Session,
    report: MachineReport,
    customer_id: uuid.UUID,
    hours: Decimal,
    machine_id: uuid.UUID | None,
) -> list[tuple[HoursPurchase, uuid.UUID, Decimal]]:
    """Consume `hours` of the customer's hours FIFO for an approved report; returns (order, lot machine, hours)."""
    taken: list[tuple[HoursPurchase, uuid.UUID, Decimal]] = []
    left = hours
    for purchase in _fifo_purchases(session, customer_id):
        if left <= 0:
            break
        totals = purchase_totals(session, purchase)
        machines = (
            [machine_id]
            if machine_id is not None
            else [
                purchase.machine_id,
                *sorted((m for m in totals.machines if m != purchase.machine_id), key=str),
            ]
        )
        for lot_machine in machines:
            if left <= 0:
                break
            take = min(totals.remaining_on(lot_machine), left)
            if take <= 0:
                continue
            engine.ledger.add(
                purchase,
                lot_machine,
                LedgerEntryType.CONSUMED,
                take,
                reason=f"Machine report {report.report_number}",
                policy_version=engine.eff.version_stamp,
                machine_report_id=report.id,
            )
            taken.append((purchase, lot_machine, take))
            left -= take
    return taken
