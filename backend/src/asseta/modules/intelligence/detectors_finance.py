"""Finance detectors: duplicate receipts, fuel allowance, weekly machine spending and cash custody held too long.
Data loading only (tenant RLS scope); decisions live in the pure rules."""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.db import DbScope
from asseta.modules.expenses.models import Expense, ExpenseAttachment, ExpenseStatus, FuelEvent, FuelEventType
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.common import tenant_settings
from asseta.modules.fleet.models import StaffKind, StaffMember
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.rules import (
    CustodyPosition,
    FuelWindow,
    MachineWeekSpend,
    ReceiptUse,
    SignalFinding,
    cash_not_handed_over,
    duplicate_receipts,
    expense_threshold_exceeded,
    fuel_allowance_exceeded,
)
from asseta.modules.machine_reports.models import MachineReport, MachineReportStatus
from asseta.modules.meter.models import CaptureAttachment
from asseta.modules.policy.schemas import FraudControlsPolicy
from asseta.modules.policy.service import EffectivePolicy, PolicyService

COUNTED_SPEND = (ExpenseStatus.APPROVED, ExpenseStatus.PENDING_APPROVAL)


# --- DUPLICATE_RECEIPT -----------------------------------------------------------------------------------------
def _receipt_uses(s: Session, shas: set[str]) -> list[ReceiptUse]:
    rows = s.execute(
        select(Expense, CaptureAttachment.sha256)
        .join(ExpenseAttachment, ExpenseAttachment.expense_id == Expense.id)
        .join(CaptureAttachment, CaptureAttachment.id == ExpenseAttachment.attachment_id)
        .where(CaptureAttachment.sha256.in_(shas))
    ).all()
    return [
        ReceiptUse(
            e.id,
            sha,
            e.incurred_at,
            e.submitted_at,
            e.submitted_by,
            e.custodian_staff_id,
            e.machine_id,
            e.amount,
            e.currency,
        )
        for e, sha in rows
    ]


def detect_duplicate_receipts(
    s: Session, eff: EffectivePolicy[FraudControlsPolicy], since: datetime, expense_ids: set[uuid.UUID] | None = None
) -> list[SignalFinding]:
    """Receipts on expenses submitted since `since` (or the given expenses) whose image hash is on another expense.
    Any receipt linked through `expense_attachment` counts, whatever purpose it was uploaded under."""
    stmt = (
        select(Expense.id, CaptureAttachment.sha256)
        .join(ExpenseAttachment, ExpenseAttachment.expense_id == Expense.id)
        .join(CaptureAttachment, CaptureAttachment.id == ExpenseAttachment.attachment_id)
    )
    stmt = (
        stmt.where(Expense.id.in_(expense_ids))
        if expense_ids is not None
        else stmt.where(Expense.submitted_at >= since)
    )
    candidates = s.execute(stmt).all()
    if not candidates:
        return []
    uses = _receipt_uses(s, {sha for _, sha in candidates})
    return duplicate_receipts(
        uses, eff.policy.duplicate_receipt_lookback_days, eff.version_stamp, {eid for eid, _ in candidates}
    )


# --- FUEL_ALLOWANCE_EXCEEDED -----------------------------------------------------------------------------------
def detect_fuel_allowance(s: Session, tenant_id: uuid.UUID, since: datetime) -> list[SignalFinding]:
    """Per approved machine report: fuel on the machine over the report's period (previous reading to its reading)
    vs the meter hours it reports."""
    policies, out = PolicyService(s), []
    reports = s.execute(
        select(MachineReport).where(
            MachineReport.status == MachineReportStatus.APPROVED,
            MachineReport.hours > 0,
            MachineReport.decided_at >= since,
        )
    ).scalars()
    for report in reports:
        eff = policies.fraud_controls(tenant_id, report.machine_id, at=report.end_at)
        if eff.policy.fuel_max_litres_per_meter_hour is None:
            continue
        fuel = list(
            s.execute(
                select(FuelEvent).where(
                    FuelEvent.machine_id == report.machine_id,
                    FuelEvent.occurred_at >= report.start_at,
                    FuelEvent.occurred_at <= report.end_at,
                )
            ).scalars()
        )
        into = sum((f.litres for f in fuel if f.event_type is not FuelEventType.USAGE), Decimal(0))
        used = sum((f.litres for f in fuel if f.event_type is FuelEventType.USAGE), Decimal(0))
        window = FuelWindow(
            report.machine_id,
            report.id,
            report.report_number,
            report.start_reading,
            report.end_reading,
            report.start_at,
            report.end_at,
            into,
            used,
            tuple(f.id for f in fuel),
            tuple(f.recorded_by for f in fuel if f.recorded_by),
        )
        if finding := fuel_allowance_exceeded(window, eff.policy.fuel_max_litres_per_meter_hour, eff.version_stamp):
            out.append(finding)
    return out


# --- EXPENSE_THRESHOLD_EXCEEDED --------------------------------------------------------------------------------
def _iso_weeks(tz: ZoneInfo, since: datetime, now: datetime) -> list[tuple[date, datetime, datetime]]:
    """Tenant-local ISO weeks (Monday 00:00) overlapping [since, now], as UTC instants."""
    first = since.astimezone(tz).date()
    monday = first - timedelta(days=first.weekday())
    weeks: list[tuple[date, datetime, datetime]] = []
    while True:
        start = datetime.combine(monday, time.min, tz).astimezone(UTC)
        if start > now:
            return weeks
        weeks.append((monday, start, datetime.combine(monday + timedelta(days=7), time.min, tz).astimezone(UTC)))
        monday += timedelta(days=7)


def detect_expense_threshold(s: Session, tenant_id: uuid.UUID, now: datetime, since: datetime) -> list[SignalFinding]:
    """Approved + pending expenses per machine per tenant-local ISO week, in the tenant base currency only."""
    settings = tenant_settings(s, tenant_id)
    policies, out = PolicyService(s), []
    for monday, start, end in _iso_weeks(ZoneInfo(settings.timezone), since, now):
        rows = s.execute(
            select(Expense).where(
                Expense.machine_id.is_not(None),
                Expense.status.in_(COUNTED_SPEND),
                Expense.currency == settings.currency,
                Expense.incurred_at >= start,
                Expense.incurred_at < end,
            )
        ).scalars()
        by_machine: dict[uuid.UUID, list[Expense]] = defaultdict(list)
        for e in rows:
            assert e.machine_id is not None
            by_machine[e.machine_id].append(e)
        iso = monday.isocalendar()
        for machine_id, expenses in by_machine.items():
            eff = policies.fraud_controls(tenant_id, machine_id, at=min(end, now))
            spend = MachineWeekSpend(
                machine_id,
                iso.year,
                iso.week,
                start,
                end,
                settings.currency,
                sum((e.amount for e in expenses), Decimal(0)),
                tuple(e.id for e in expenses),
                tuple(e.submitted_by for e in expenses if e.submitted_by),
            )
            threshold = eff.policy.expense_threshold_per_machine_per_week
            if (finding := expense_threshold_exceeded(spend, threshold, eff.version_stamp)) is not None:
                out.append(finding)
    return out


# --- CASH_NOT_HANDED_OVER --------------------------------------------------------------------------------------
def detect_cash_not_handed_over(
    s: Session, tenant_id: uuid.UUID, now: datetime, eff: EffectivePolicy[FraudControlsPolicy]
) -> list[SignalFinding]:
    """Uses the cash reconciliation formula (CashCustodyService) for every supervisor and currency held."""
    ctx = RequestContext(uuid.UUID(int=0), "system:intelligence", DbScope.TENANT, tenant_id, frozenset(), frozenset())
    custody, out = CashCustodyService(s, ctx, now), []
    for staff in s.execute(select(StaffMember).where(StaffMember.kind == StaffKind.SUPERVISOR)).scalars():
        user_id = (
            s.execute(select(AppUser.id).where(AppUser.keycloak_subject == staff.keycloak_subject)).scalar_one_or_none()
            if staff.keycloak_subject
            else None
        )
        for bal in custody.balances(staff.id):
            outstanding, since = custody.outstanding_since(staff.id, bal.currency)
            if since is None:
                continue
            pos = CustodyPosition(staff.id, user_id, bal.currency, outstanding, since, now)
            out += cash_not_handed_over(
                pos, eff.policy.cash_outstanding_max_hours, eff.policy.cash_outstanding_max_amount, eff.version_stamp
            )
    return out
