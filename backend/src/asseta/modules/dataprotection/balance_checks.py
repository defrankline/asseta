"""Recomputes a tenant's balances from their underlying records and compares them with every stored or snapshotted
figure (guideline 6, 9). Pure reads inside the caller's transaction: nothing is corrected, the ledger prevails.

A snapshot is a figure written when something was posted (`resulting_balance`, a low-balance alert). Hours are
compared as of that moment, because ledger rows are immutable and carry when they were recorded. Money snapshots
(custody, receivable) are compared only while no later activity touched that balance; a later record would legitimately
move it and says nothing about the snapshot."""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.modules.adjustments.models import (
    AdjustmentEntryStatus,
    AdjustmentLedgerEntry,
    AdjustmentType,
    AdjustmentUnit,
)
from asseta.modules.dataprotection.balance_money import check_cash, check_invoices, check_receivables
from asseta.modules.dataprotection.balance_report import ZERO, CheckKind, Finding, Report, differs
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.ledger import purchase_totals
from asseta.modules.hours.models import SIGN, HoursLedgerEntry, HoursLowBalanceAlert, HoursPurchase
from asseta.modules.meter.allocation_models import AllocationSource, AllocationStatus, DailyOperationalReport
from asseta.modules.meter.allocation_models import WorkAllocation as Alloc
from asseta.modules.meter.allocation_writer import AllocationWriter
from asseta.modules.meter.allocation_writer import tenant_zone as allocation_zone
from asseta.modules.meter.engine_hours import engine_hours_on, load_machine_ledger

NEW_ALLOCATION_LAG_DAYS = 3  # a recent day with no allocation yet is the sweep still catching up, not a mismatch


# --- customer hours per lot ----------------------------------------------------------------------------------------
def _signed_sum(s: Session, purchase_id: uuid.UUID, machine_id: uuid.UUID, as_of: datetime | None) -> Decimal:
    conds = [HoursLedgerEntry.purchase_id == purchase_id, HoursLedgerEntry.machine_id == machine_id]
    if as_of is not None:
        conds.append(HoursLedgerEntry.created_at <= as_of)
    total = ZERO
    for entry_type, hours in s.execute(
        select(HoursLedgerEntry.entry_type, func.sum(HoursLedgerEntry.hours))
        .where(*conds)
        .group_by(HoursLedgerEntry.entry_type)
    ):
        total += SIGN[entry_type] * Decimal(hours)
    return total


HOURS_SNAPSHOTS = (AdjustmentType.HOURS_TRANSFER, AdjustmentType.HOURS_CORRECTION, AdjustmentType.HOURS_REFUND)


def _check_hours(s: Session, r: Report) -> None:
    purchases = {p.id: p for p in s.execute(select(HoursPurchase)).scalars()}
    for purchase in purchases.values():
        totals = purchase_totals(s, purchase)
        for machine_id, machine_totals in totals.machines.items():
            r.checked[CheckKind.CUSTOMER_HOURS_LOT] += 1
            recomputed = _signed_sum(s, purchase.id, machine_id, None)
            label = f"{purchase.purchase_number} on {_machine_code(s, machine_id)}"
            if differs(recomputed, machine_totals.remaining):
                r.findings.append(
                    _lot_finding(purchase, machine_id, label, recomputed, machine_totals.remaining, "displayed balance")
                )
            if recomputed < ZERO:
                r.findings.append(_lot_finding(purchase, machine_id, label, recomputed, ZERO, "negative lot balance"))
    entries = s.execute(
        select(AdjustmentLedgerEntry).where(
            AdjustmentLedgerEntry.unit == AdjustmentUnit.HOURS,
            AdjustmentLedgerEntry.status == AdjustmentEntryStatus.APPROVED,
            AdjustmentLedgerEntry.adjustment_type.in_(HOURS_SNAPSHOTS),
            AdjustmentLedgerEntry.original_type == "hours_purchase",
            AdjustmentLedgerEntry.new_value.is_not(None),
        )
    ).scalars()
    for e in entries:
        p = purchases.get(e.original_id)
        if p is None or e.new_value is None:
            continue
        machine_id = e.machine_id or p.machine_id
        r.checked[CheckKind.CUSTOMER_HOURS_LOT] += 1
        at_post = _signed_sum(s, p.id, machine_id, e.posted_at)
        if differs(at_post, e.new_value):
            label = f"{p.purchase_number} on {_machine_code(s, machine_id)}"
            r.findings.append(_lot_finding(p, machine_id, label, at_post, e.new_value, f"adjustment {e.id} new_value"))
    for alert in s.execute(select(HoursLowBalanceAlert)).scalars():
        p = purchases.get(alert.purchase_id)
        if p is None:
            continue
        r.checked[CheckKind.CUSTOMER_HOURS_LOT] += 1
        total = sum(
            (_signed_sum(s, p.id, m, alert.created_at) for m in purchase_totals(s, p).machines),
            ZERO,
        )
        if differs(total, alert.remaining_hours):
            r.findings.append(
                _lot_finding(p, alert.machine_id, p.purchase_number, total, alert.remaining_hours, "low-balance alert")
            )


def _machine_code(s: Session, machine_id: uuid.UUID) -> str:
    machine = s.get(Machine, machine_id)
    return machine.asset_code if machine else str(machine_id)


def _lot_finding(
    p: HoursPurchase, machine_id: uuid.UUID, label: str, ledger: Decimal, stored: Decimal, source: str
) -> Finding:
    return Finding(
        CheckKind.CUSTOMER_HOURS_LOT,
        "hours_purchase",
        str(p.id),
        label,
        ledger,
        stored,
        None,
        source,
        {"machine_id": str(machine_id), "customer_id": str(p.customer_id)},
    )


# --- engine hours per machine --------------------------------------------------------------------------------------
def _check_engine(s: Session, r: Report, now: datetime) -> None:
    if not engine_hours_on(s, r.tenant_id, now):
        return
    today = now.astimezone(allocation_zone(s, r.tenant_id)).date()
    stored: dict[uuid.UUID, dict[date, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for machine_id, day, hours in s.execute(
        select(Alloc.machine_id, Alloc.work_date, func.sum(Alloc.hours))
        .where(Alloc.status == AllocationStatus.ACTIVE)
        .group_by(Alloc.machine_id, Alloc.work_date)
    ):
        stored[machine_id][day] = Decimal(hours)
    writer = AllocationWriter(s, r.tenant_id, now, AllocationSource.DERIVED)
    for machine in s.execute(select(Machine).where(Machine.id.in_(list(stored)))).scalars():
        plan = writer.build_plan(load_machine_ledger(s, r.tenant_id, machine, now))
        planned: dict[date, Decimal] = defaultdict(lambda: ZERO)
        for entry in plan.entries:
            planned[entry.work_date] += entry.hours
        by_day = stored[machine.id]
        for day in sorted(d for d in set(planned) | set(by_day) if d < today):
            if day not in by_day and day >= today - timedelta(days=NEW_ALLOCATION_LAG_DAYS):
                continue  # the allocation sweep has not reached this day yet
            r.checked[CheckKind.ENGINE_HOURS] += 1
            ledger, kept = planned.get(day, ZERO), by_day.get(day, ZERO)
            if differs(ledger, kept):
                r.findings.append(
                    Finding(
                        CheckKind.ENGINE_HOURS,
                        "machine",
                        str(machine.id),
                        f"{machine.asset_code} on {day.isoformat()}",
                        ledger,
                        kept,
                        None,
                        "work allocations (active total for the day)",
                        {"work_date": day.isoformat()},
                    )
                )


def _check_daily_reports(s: Session, r: Report) -> None:
    for report in s.execute(select(DailyOperationalReport)).scalars():
        r.checked[CheckKind.DAILY_REPORT] += 1
        from_readings = report.closing_reading - report.opening_reading
        if from_readings >= ZERO and differs(from_readings, report.total_hours):
            r.findings.append(_report_finding(s, report, from_readings, report.total_hours, "report total_hours"))
        parts = report.billable_hours + report.unbillable_hours + report.difference_hours
        if differs(report.total_hours, parts):
            r.findings.append(
                _report_finding(s, report, report.total_hours, parts, "billable + unbillable + difference")
            )


def _report_finding(
    s: Session, report: DailyOperationalReport, ledger: Decimal, stored: Decimal, source: str
) -> Finding:
    return Finding(
        CheckKind.DAILY_REPORT,
        "daily_operational_report",
        str(report.id),
        f"{_machine_code(s, report.machine_id)} on {report.report_date.isoformat()}",
        ledger,
        stored,
        None,
        source,
        {"report_date": report.report_date.isoformat(), "machine_id": str(report.machine_id)},
    )


def verify_tenant(s: Session, tenant_id: uuid.UUID, now: datetime) -> Report:
    """Every check for one tenant, in the caller's (tenant-scoped) transaction. Read-only."""
    report = Report(tenant_id, now)
    _check_hours(s, report)
    _check_engine(s, report, now)
    _check_daily_reports(s, report)
    check_cash(s, report, now)
    check_receivables(s, report)
    check_invoices(s, report)
    return report
