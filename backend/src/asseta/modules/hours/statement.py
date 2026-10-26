"""Customer hours statement (DEC-031 P3): what a customer bought, had activated, used (per day and job), transferred,
lost to expiry or cancellation, and has left — for a tenant-local period, optionally for one machine. A read model
over the hours ledger (nothing stored); the PDF is the same statement on the report layout.

Days: a daily-drawdown entry (PROVISIONAL) counts on the day of use it was drawn for; every other entry on the
tenant-local day it was written. Usage lines: DAILY = drawn day by day while the job ran (net of corrections);
FINAL = the final allocation at completion less what was drawn daily (all of a job's hours when it was allocated at
completion). Their sum is the period's use, so opening + movements = closing always holds."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.modules.accountability.names import fill_names
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.dto import (
    HoursStatementDto,
    HoursStatementLineDto,
    HoursStatementPurchaseDto,
    HoursStatementTotalsDto,
    HoursStatementUsageDto,
)
from asseta.modules.hours.ledger import ZERO, derived_status, due_to_expire, next_expiry, purchase_totals
from asseta.modules.hours.models import SIGN, HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.jobs.models import Customer, Job, JobStatus
from asseta.modules.reports.definitions import ReportEnv, format_value
from asseta.modules.reports.render import PdfColumn, PdfSection, document_pdf

T = LedgerEntryType
MAX_DAYS = 366
USED = (T.CONSUMED, T.PROVISIONAL, T.PROVISIONAL_REVERSED)


@dataclass(frozen=True)
class StatementQuery:
    customer_id: uuid.UUID
    machine_id: uuid.UUID | None
    date_from: date
    date_to: date


def default_period(today: date) -> tuple[date, date]:
    return today.replace(day=1), today


def _day(e: HoursLedgerEntry, tz: ZoneInfo) -> date:
    if e.entry_type is T.PROVISIONAL and e.usage_day is not None:
        return e.usage_day
    return e.occurred_at.astimezone(tz).date()


def _local_day(at: datetime, tz: ZoneInfo) -> date:
    return at.astimezone(tz).date()


def build_statement(s: Session, tz: ZoneInfo, q: StatementQuery, now: datetime, pdf_path: str) -> HoursStatementDto:
    if q.date_to < q.date_from:
        raise BusinessRuleViolation("The period ends before it starts", code="INVALID_PERIOD")
    if (q.date_to - q.date_from).days >= MAX_DAYS:
        raise BusinessRuleViolation(f"A statement covers at most {MAX_DAYS} days", code="PERIOD_TOO_LONG")
    if s.get(Customer, q.customer_id) is None:
        raise NotFound("Customer not found")
    if q.machine_id is not None and s.get(Machine, q.machine_id) is None:
        raise NotFound("Machine not found")
    stmt = select(HoursLedgerEntry).where(HoursLedgerEntry.customer_id == q.customer_id)
    if q.machine_id is not None:
        stmt = stmt.where(HoursLedgerEntry.machine_id == q.machine_id)
    entries = sorted(s.execute(stmt).scalars(), key=lambda e: (_day(e, tz), e.occurred_at, e.created_at, str(e.id)))
    before = [e for e in entries if _day(e, tz) < q.date_from]
    inside = [e for e in entries if q.date_from <= _day(e, tz) <= q.date_to]
    opening = sum((SIGN[e.entry_type] * e.hours for e in before), ZERO)

    by_type: dict[LedgerEntryType, Decimal] = defaultdict(lambda: ZERO)
    for e in inside:
        by_type[e.entry_type] += e.hours
    used = by_type[T.CONSUMED] + by_type[T.PROVISIONAL] - by_type[T.PROVISIONAL_REVERSED]
    upto = [e for e in entries if _day(e, tz) <= q.date_to]
    provisional_at_close = sum(
        (e.hours * -SIGN[e.entry_type] for e in upto if e.entry_type in (T.PROVISIONAL, T.PROVISIONAL_REVERSED)), ZERO
    )

    lines: list[HoursStatementLineDto] = []
    balance = opening
    purchase_numbers = dict(
        s.execute(
            select(HoursPurchase.id, HoursPurchase.purchase_number).where(HoursPurchase.customer_id == q.customer_id)
        ).all()
    )
    for e in inside:
        signed = SIGN[e.entry_type] * e.hours
        balance += signed
        lines.append(
            HoursStatementLineDto(
                entry_id=e.id,
                day=_day(e, tz),
                occurred_at=e.occurred_at,
                entry_type=e.entry_type,
                purchase_id=e.purchase_id,
                purchase_number=purchase_numbers.get(e.purchase_id),
                machine_id=e.machine_id,
                job_id=e.job_id,
                hours=signed,
                balance_after=balance,
                reason=e.reason,
            )
        )

    job_ids = {e.job_id for e in inside if e.job_id is not None}
    running = (
        set(s.execute(select(Job.id).where(Job.id.in_(job_ids), Job.status == JobStatus.IN_PROGRESS)).scalars())
        if job_ids
        else set()
    )
    usage: dict[tuple[date, uuid.UUID | None, uuid.UUID, str], Decimal] = defaultdict(lambda: ZERO)
    for e in inside:
        if e.entry_type not in USED:
            continue
        daily = e.entry_type is T.PROVISIONAL or (e.entry_type is T.PROVISIONAL_REVERSED and e.allocation_id is None)
        usage[(_day(e, tz), e.job_id, e.machine_id, "DAILY" if daily else "FINAL")] += -SIGN[e.entry_type] * e.hours
    usage_lines = [
        HoursStatementUsageDto(
            day=day,
            job_id=job_id,
            machine_id=machine_id,
            hours=hours,
            basis="DAILY" if basis == "DAILY" else "FINAL",
            job_running=job_id in running,
        )
        for (day, job_id, machine_id, basis), hours in sorted(
            usage.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][3])
        )
        if hours != 0
    ]

    end = datetime.combine(q.date_to + timedelta(days=1), time(), tz)
    start = datetime.combine(q.date_from, time(), tz)
    pstmt = select(HoursPurchase).where(HoursPurchase.customer_id == q.customer_id, HoursPurchase.created_at < end)
    purchases = list(s.execute(pstmt.order_by(HoursPurchase.created_at, HoursPurchase.purchase_number)).scalars())
    on_machine = {e.purchase_id for e in entries}
    if q.machine_id is not None:
        purchases = [p for p in purchases if p.machine_id == q.machine_id or p.id in on_machine]
    bought = sum((p.hours for p in purchases if p.created_at >= start and (q.machine_id in (None, p.machine_id))), ZERO)
    purchase_rows: list[HoursStatementPurchaseDto] = []
    awaiting = ZERO
    for p in purchases:
        if p.cancelled_at is not None and p.cancelled_at < start and p.id not in {e.purchase_id for e in inside}:
            continue  # cancelled before the period with nothing in it
        totals = purchase_totals(s, p)
        if p.cancelled_at is None and q.machine_id in (None, p.machine_id):
            awaiting += max(ZERO, p.hours - totals.net_activated)
        soon = next_expiry(s, p.id, now) if p.cancelled_at is None else None
        purchase_rows.append(
            HoursStatementPurchaseDto(
                purchase_id=p.id,
                purchase_number=p.purchase_number,
                machine_id=p.machine_id,
                bought_at=p.created_at,
                hours=p.hours,
                currency=p.currency,
                effective_rate=p.effective_rate,
                amount=p.amount,
                status=derived_status(p, totals),
                activated=totals.activated,
                remaining_at_close=sum((SIGN[e.entry_type] * e.hours for e in upto if e.purchase_id == p.id), ZERO),
                next_expiry_at=soon,
                expiring_hours=due_to_expire(s, p, totals, soon) if soon is not None else ZERO,
                cancelled_at=p.cancelled_at,
            )
        )
    closing = balance
    dto = HoursStatementDto(
        customer_id=q.customer_id,
        machine_id=q.machine_id,
        date_from=q.date_from,
        date_to=q.date_to,
        timezone=str(tz),
        generated_at=now,
        totals=HoursStatementTotalsDto(
            opening_balance=opening,
            bought=bought,
            activated=by_type[T.ACTIVATED],
            used=used,
            transferred_in=by_type[T.TRANSFER_IN],
            transferred_out=by_type[T.TRANSFER_OUT],
            expired=by_type[T.EXPIRED],
            cancelled=by_type[T.REVERSAL],
            closing_balance=closing,
            provisional_at_close=provisional_at_close,
            awaiting_activation=awaiting,
        ),
        purchases=purchase_rows,
        usage=usage_lines,
        lines=lines,
        pdf_path=pdf_path,
    )
    return fill_names(s, dto)


def _h(v: Decimal) -> str:
    return format_value(v, "decimal", "UTC", human=True)


def statement_pdf(dto: HoursStatementDto, env: ReportEnv) -> bytes:
    def machine(code: str | None, name: str | None) -> str:
        return " - ".join(x for x in (code, name) if x) or "-"

    t = dto.totals
    scope = f"Machine: {machine(dto.machine_code, dto.machine_name)}" if dto.machine_id else "All machines"
    meta = [
        f"Customer: {dto.customer_name or dto.customer_id}",
        scope,
        f"Period: {dto.date_from.isoformat()} to {dto.date_to.isoformat()} ({dto.timezone})",
    ]
    summary = [
        ("Opening balance (hours)", _h(t.opening_balance)),
        ("Bought in the period", _h(t.bought)),
        ("Activated (paid or on credit)", _h(t.activated)),
        ("Used", _h(t.used)),
        ("  of which still provisional (jobs running)", _h(t.provisional_at_close)),
        ("Transferred in", _h(t.transferred_in)),
        ("Transferred out", _h(t.transferred_out)),
        ("Expired", _h(t.expired)),
        ("Cancelled", _h(t.cancelled)),
        ("Remaining at the end of the period", _h(t.closing_balance)),
        ("Bought, awaiting payment / activation", _h(t.awaiting_activation)),
    ]
    tz = dto.timezone
    sections = [
        PdfSection(
            "Purchases",
            (
                PdfColumn("Purchase", 14),
                PdfColumn("Machine", 18),
                PdfColumn("Bought", 14),
                PdfColumn("Hours", 8, True),
                PdfColumn("Amount", 14, True),
                PdfColumn("Status", 12),
                PdfColumn("Remaining", 9, True),
                PdfColumn("Next expiry", 14),
                PdfColumn("Expiring", 8, True),
            ),
            [
                [
                    p.purchase_number or str(p.purchase_id),
                    machine(p.machine_code, p.machine_name),
                    format_value(p.bought_at, "instant", tz, human=True),
                    _h(p.hours),
                    f"{format_value(p.amount, 'money', tz, human=True)} {p.currency}",
                    p.status,
                    _h(p.remaining_at_close),
                    format_value(p.next_expiry_at, "instant", tz, human=True) or "-",
                    _h(p.expiring_hours),
                ]
                for p in dto.purchases
            ],
        ),
        PdfSection(
            "Hours used per day and job",
            (
                PdfColumn("Day", 12),
                PdfColumn("Job", 14),
                PdfColumn("Machine", 22),
                PdfColumn("Basis", 18),
                PdfColumn("Hours", 10, True),
            ),
            [
                [
                    u.day.isoformat(),
                    u.job_number or "-",
                    machine(u.machine_code, u.machine_name),
                    ("Daily drawdown" if u.basis == "DAILY" else "Final allocation")
                    + (" (job running)" if u.job_running else ""),
                    _h(u.hours),
                ]
                for u in dto.usage
            ],
        ),
        PdfSection(
            "Movements",
            (
                PdfColumn("Day", 11),
                PdfColumn("Movement", 18),
                PdfColumn("Purchase", 14),
                PdfColumn("Machine", 16),
                PdfColumn("Job", 11),
                PdfColumn("Hours", 9, True),
                PdfColumn("Balance", 9, True),
            ),
            [
                [
                    line.day.isoformat(),
                    line.entry_type.value.replace("_", " ").capitalize(),
                    line.purchase_number or "-",
                    machine(line.machine_code, line.machine_name),
                    line.job_number or "-",
                    _h(line.hours),
                    _h(line.balance_after),
                ]
                for line in dto.lines
            ],
        ),
    ]
    return document_pdf("Customer hours statement", env, meta, summary, sections)
