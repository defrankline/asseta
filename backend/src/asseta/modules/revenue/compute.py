"""Hours-to-money arithmetic (DEC-031 R2/R3) as pure, deterministic functions of plain facts — nothing is stored.

Expected revenue of a job in a time window = its customer-work engine hours in the window (after the revenue-hour
basis, R1) x the job's locked hourly rate, + standby hours x the standby rate (STANDBY_RATE contracts only), + the
mobilization fee in the window containing the job's start; less the job's approved discount (as on its charges).
Tax is never part of revenue. A ledger interval that spans window boundaries is split by wall-clock overlap.

Money attributed to a job = its issued invoice lines (hire, standby, mobilization, discount — never tax) + its
prepaid hours consumed x the purchase effective rate. A job's money is spread over windows in proportion to its
expected revenue, so a job paid in full shows no difference in any window. Jobs still running carry their expected
revenue as `in_progress` (not yet billable) instead of a difference.

Engine hours outside jobs that nobody has had approved as non-customer activity (owner rule, 2026-10-26) are
expected revenue too, at the tenant's chosen rate (machine rate card or a tenant rate) — or only shown when the
tenant excludes them."""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

ZERO = Decimal(0)
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class JobTerms:
    job_id: uuid.UUID
    job_number: str
    customer_id: uuid.UUID | None
    site_id: uuid.UUID | None
    currency: str
    hourly_rate: Decimal
    discount_percent: Decimal
    standby_rate: Decimal | None  # set only for STANDBY_RATE contracts
    mobilization_fee: Decimal
    started_at: datetime
    completed: bool


@dataclass(frozen=True)
class WorkPiece:
    """Customer-work engine hours of one ledger interval (net of non-revenue time) on one job."""

    job_id: uuid.UUID
    start: datetime
    end: datetime
    hours: Decimal


@dataclass(frozen=True)
class TimeSpan:
    """A wall-clock window of one job (e.g. a non-billable STANDBY work-log entry)."""

    job_id: uuid.UUID
    start: datetime
    end: datetime


@dataclass(frozen=True)
class MoneyItem:
    """One source of money for a job: an issued invoice line or a prepaid consumption (hours x effective rate)."""

    job_id: uuid.UUID
    source: str  # INVOICE_LINE | PREPAID_CONSUMPTION
    ref_id: uuid.UUID  # invoice line id | hours ledger entry id
    parent_id: uuid.UUID  # invoice id | purchase id
    currency: str
    amount: Decimal
    hours: Decimal | None = None


@dataclass
class WindowMoney:
    currency: str
    expected: Decimal = ZERO
    in_progress: Decimal = ZERO  # expected revenue of jobs still running (not yet billable)
    attributed: Decimal = ZERO
    unexplained_hours: Decimal = ZERO  # engine hours outside jobs not approved as non-customer activity
    unexplained_expected: Decimal = ZERO  # part of `expected` (0 when the tenant excludes those hours)
    job_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def shortfall(self) -> Decimal:
        """Expected (of completed work) not matched by attributed money; negative = more money than expected."""
        return self.expected - self.in_progress - self.attributed


def overlap_fraction(start: datetime, end: datetime, w0: datetime | None, w1: datetime | None) -> Decimal:
    """Share of [start, end] inside [w0, w1) (None = unbounded). A zero-length span counts where it starts."""
    lo = start if w0 is None else max(start, w0)
    hi = end if w1 is None else min(end, w1)
    total = (end - start).total_seconds()
    if total <= 0:
        inside = (w0 is None or start >= w0) and (w1 is None or start < w1)
        return Decimal(1) if inside else ZERO
    part = (hi - lo).total_seconds()
    if part <= 0:
        return ZERO
    return Decimal(str(part)) / Decimal(str(total))


def overlap_hours(start: datetime, end: datetime, w0: datetime | None, w1: datetime | None) -> Decimal:
    lo = start if w0 is None else max(start, w0)
    hi = end if w1 is None else min(end, w1)
    seconds = (hi - lo).total_seconds()
    return Decimal(str(seconds)) / Decimal(3600) if seconds > 0 else ZERO


def in_window(at: datetime, w0: datetime | None, w1: datetime | None) -> bool:
    return (w0 is None or at >= w0) and (w1 is None or at < w1)


def job_expected(
    terms: JobTerms,
    pieces: Iterable[WorkPiece],
    standby: Iterable[TimeSpan],
    w0: datetime | None,
    w1: datetime | None,
) -> Decimal:
    hours = sum((p.hours * overlap_fraction(p.start, p.end, w0, w1) for p in pieces if p.job_id == terms.job_id), ZERO)
    gross = hours * terms.hourly_rate
    if terms.standby_rate is not None:
        sb = sum((overlap_hours(s.start, s.end, w0, w1) for s in standby if s.job_id == terms.job_id), ZERO)
        gross += sb * terms.standby_rate
    if terms.mobilization_fee > 0 and in_window(terms.started_at, w0, w1):
        gross += terms.mobilization_fee
    return gross * (HUNDRED - terms.discount_percent) / HUNDRED


@dataclass
class MachineRevenue:
    """Everything needed to reconcile one machine's hours with money, over any window."""

    jobs: Sequence[JobTerms]
    pieces: Sequence[WorkPiece]
    standby: Sequence[TimeSpan]
    money: Sequence[MoneyItem]
    unexplained: Sequence[TimeSpan] = ()  # unexplained intervals outside jobs (job_id unused)
    unexplained_hours: Sequence[Decimal] = ()  # their engine hours (same order)
    unexplained_rate: tuple[str, Decimal] | None = None  # (currency, rate); None: not expected as revenue
    _totals: dict[uuid.UUID, Decimal] = field(default_factory=dict)

    def _total_expected(self, terms: JobTerms) -> Decimal:
        if terms.job_id not in self._totals:
            self._totals[terms.job_id] = job_expected(terms, self.pieces, self.standby, None, None)
        return self._totals[terms.job_id]

    def job_money(self, job_id: uuid.UUID) -> Decimal:
        return sum((m.amount for m in self.money if m.job_id == job_id), ZERO)

    def window(
        self,
        w0: datetime | None,
        w1: datetime | None,
        job_ids: set[uuid.UUID] | None = None,
        include_unexplained: bool = True,
    ) -> dict[str, WindowMoney]:
        """Expected / in-progress / attributed per currency for the window (optionally only some jobs), plus the
        revenue expected from unexplained engine hours outside jobs."""
        out: dict[str, WindowMoney] = {}
        for terms in self.jobs:
            if job_ids is not None and terms.job_id not in job_ids:
                continue
            expected = job_expected(terms, self.pieces, self.standby, w0, w1)
            total = self._total_expected(terms)
            money = self.job_money(terms.job_id)
            if total > 0:
                attributed = money * expected / total
            else:  # no expected revenue at all (e.g. minimum-hours billing only): money counts where the job starts
                attributed = money if in_window(terms.started_at, w0, w1) else ZERO
            if expected == 0 and attributed == 0:
                continue
            w = out.setdefault(terms.currency, WindowMoney(terms.currency))
            w.expected += expected
            w.attributed += attributed
            if not terms.completed:
                w.in_progress += expected
            w.job_ids.append(terms.job_id)
        if include_unexplained and self.unexplained:
            hours = sum(
                (
                    h * overlap_fraction(u.start, u.end, w0, w1)
                    for u, h in zip(self.unexplained, self.unexplained_hours, strict=True)
                ),
                ZERO,
            )
            if hours > 0:
                currency, rate = self.unexplained_rate or ("", ZERO)
                if self.unexplained_rate is None:  # shown, not expected: attach to any currency in the window
                    currency = next(iter(out), "")
                if currency:
                    w = out.setdefault(currency, WindowMoney(currency))
                    w.unexplained_hours += hours
                    w.unexplained_expected += hours * rate
                    w.expected += hours * rate
        return out
