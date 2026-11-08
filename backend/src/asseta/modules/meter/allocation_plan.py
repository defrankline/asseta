"""Turns a machine's engine-hour ledger into work-allocation pieces (DEC-032 A1), as a pure function of plain facts.

Each ledger interval is laid out on a line of its engine hours. The line is cut two ways: by meter base and
tenant-local day (wall-clock share, cumulative rounding, so pieces abut exactly) and by allocation (customer work,
then non-revenue activity, then unexplained). Each intersection is one entry with its own meter range. Hours whose
meter range was already allocated (a reading went down and no reset was approved) are not allocated twice: they stay
in the day's total and show as a difference until someone corrects the reading or approves a reset."""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from asseta.modules.meter.allocation_models import AllocationKind
from asseta.modules.meter.ledger import ZERO, LedgerInterval, ResetPoint, SegmentClassification, SegmentKind

STEP = Decimal("0.01")


@dataclass
class PlannedEntry:
    key: str
    work_date: date
    start_ref: uuid.UUID
    end_ref: uuid.UUID
    start_reading: Decimal
    end_reading: Decimal
    start_at: datetime
    end_at: datetime
    meter_epoch: int
    hours: Decimal
    kind: AllocationKind
    customer_id: uuid.UUID | None
    job_id: uuid.UUID | None
    activity_type: str | None
    reason_id: uuid.UUID | None
    classification_id: uuid.UUID | None
    changeover_id: uuid.UUID | None
    reading_review: str
    approval_ref_type: str | None = None
    approval_ref_ids: list[uuid.UUID] = field(default_factory=list)
    lots: list[dict[str, str]] = field(default_factory=list)


@dataclass
class Plan:
    entries: list[PlannedEntry]
    total_by_day: dict[date, Decimal]  # engine hours per day, including hours that could not be allocated


@dataclass(frozen=True)
class _Base:
    """A stretch of one interval on one meter base."""

    epoch: int
    start_at: datetime
    end_at: datetime
    start_reading: Decimal
    size: Decimal
    line_start: Decimal


@dataclass(frozen=True)
class _Piece:
    base: _Base
    day: date
    lo: Decimal
    hi: Decimal
    at: datetime
    until: datetime


@dataclass(frozen=True)
class _Bucket:
    size: Decimal
    kind: AllocationKind
    customer_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    activity_type: str | None = None
    reason_id: uuid.UUID | None = None
    classification_id: uuid.UUID | None = None
    changeover_id: uuid.UUID | None = None
    approval_ref_type: str | None = None
    approval_ref_ids: tuple[uuid.UUID, ...] = ()


def _epoch(resets: Sequence[ResetPoint], at: datetime) -> int:
    return sum(1 for r in resets if r.effective_at <= at)


def _bases(i: LedgerInterval, resets: Sequence[ResetPoint]) -> list[_Base]:
    """The interval's stretches per meter base: one, or more when an approved reset falls inside it."""
    inside = sorted((r for r in resets if i.start.at < r.effective_at <= i.end.at), key=lambda r: r.effective_at)
    whole = [_Base(_epoch(resets, i.start.at), i.start.at, i.end.at, i.start.reading, i.hours, ZERO)]
    if not inside:
        return whole
    out: list[_Base] = []
    at, reading, line, epoch = i.start.at, i.start.reading, ZERO, _epoch(resets, i.start.at)
    for r in inside:
        size = r.old_reading - reading
        out.append(_Base(epoch, at, r.effective_at, reading, size, line))
        at, reading, line, epoch = r.effective_at, r.new_reading, line + size, epoch + 1
    out.append(_Base(epoch, at, i.end.at, reading, i.end.reading - reading, line))
    return whole if any(b.size < ZERO for b in out) or sum(b.size for b in out) != i.hours else out


def _days(base: _Base, tz: ZoneInfo) -> list[_Piece]:
    """Cut one stretch at tenant-local midnights, by wall-clock share with cumulative rounding."""
    total = (base.end_at - base.start_at).total_seconds()
    first = base.start_at.astimezone(tz).date()
    last = base.end_at.astimezone(tz).date()
    if total <= 0 or first == last:
        return [_Piece(base, first, base.line_start, base.line_start + base.size, base.start_at, base.end_at)]
    out: list[_Piece] = []
    at, lo, day = base.start_at, base.line_start, first
    while True:
        midnight = datetime.combine(day + timedelta(days=1), time(), tz)
        if midnight >= base.end_at:
            if base.line_start + base.size > lo or not out:
                out.append(_Piece(base, day, lo, base.line_start + base.size, at, base.end_at))
            return out
        share = Decimal(str((midnight - base.start_at).total_seconds())) / Decimal(str(total))
        hi = base.line_start + (base.size * share).quantize(STEP, rounding=ROUND_HALF_UP)
        if hi > lo:
            out.append(_Piece(base, day, lo, hi, at, midnight))
        at, lo, day = midnight, hi, day + timedelta(days=1)


def _explained(i: LedgerInterval, size: Decimal) -> _Bucket:
    """The bucket for hours that are not customer work: an approved explanation, else UNEXPLAINED."""
    if i.approved is not None and i.classification in (
        SegmentClassification.APPROVED_NON_CUSTOMER,
        SegmentClassification.IDENTIFIED_VARIANCE,
    ):
        return _Bucket(
            size,
            AllocationKind.AUTHORIZED_ACTIVITY,
            job_id=i.job_id,
            reason_id=i.approved.reason_id,
            classification_id=i.approved.id,
            approval_ref_type="engine_hour_classification",
            approval_ref_ids=(i.approved.id,),
        )
    return _Bucket(size, AllocationKind.UNEXPLAINED, job_id=i.job_id)


def _buckets(i: LedgerInterval) -> list[_Bucket]:
    if i.kind is not SegmentKind.CUSTOMER_WORK:
        return [_explained(i, i.hours)]
    out = [
        _Bucket(
            i.customer_work_hours,
            AllocationKind.CUSTOMER_WORK,
            customer_id=i.changeover_customer_id or i.job_customer_id,
            job_id=i.billed_to_job_id or i.job_id,  # the job that bills these hours
            changeover_id=i.changeover_id,
        )
    ]
    for activity, hours in sorted(i.non_revenue.items()):
        approvals = tuple(i.non_revenue_approvals.get(activity, ()))
        out.append(
            _Bucket(
                hours,
                AllocationKind.AUTHORIZED_ACTIVITY,
                job_id=i.job_id,
                activity_type=activity,
                approval_ref_type="non_revenue_approval" if approvals else None,
                approval_ref_ids=approvals,
            )
        )
    if i.in_job_unexplained > ZERO:
        out.append(_explained(i, i.in_job_unexplained))
    return [b for b in out if b.size > ZERO]


def _entry(i: LedgerInterval, b: _Bucket, n: int, p: _Piece, m: int, lo: Decimal, hi: Decimal) -> PlannedEntry:
    start = p.base.start_reading + (lo - p.base.line_start)
    end = p.base.start_reading + (hi - p.base.line_start)
    return PlannedEntry(
        key=f"{i.start.ref}:{i.end.ref}:{p.day.isoformat()}:{n}:{m}",
        work_date=p.day,
        start_ref=i.start.ref,
        end_ref=i.end.ref,
        start_reading=start,
        end_reading=end,
        start_at=p.at,
        end_at=p.until,
        meter_epoch=p.base.epoch,
        hours=hi - lo,
        kind=b.kind,
        customer_id=b.customer_id,
        job_id=b.job_id,
        activity_type=b.activity_type,
        reason_id=b.reason_id,
        classification_id=b.classification_id,
        changeover_id=b.changeover_id,
        reading_review=i.review.value,
        approval_ref_type=b.approval_ref_type,
        approval_ref_ids=list(b.approval_ref_ids),
    )


def plan_allocations(intervals: Sequence[LedgerInterval], resets: Sequence[ResetPoint], tz: ZoneInfo) -> Plan:
    entries: list[PlannedEntry] = []
    totals: dict[date, Decimal] = defaultdict(lambda: ZERO)
    high: dict[int, Decimal] = {}  # per meter base: the top of what is already allocated
    for i in sorted(intervals, key=lambda x: (x.start.at, x.start.reading)):
        if i.hours <= ZERO or i.inconsistent:
            continue
        pieces = [p for base in _bases(i, resets) for p in _days(base, tz)]
        offset = ZERO
        for n, bucket in enumerate(_buckets(i)):
            top = offset + bucket.size
            for m, piece in enumerate(pieces):
                lo, hi = max(offset, piece.lo), min(top, piece.hi)
                if hi <= lo:
                    continue
                totals[piece.day] += hi - lo
                entry = _entry(i, bucket, n, piece, m, lo, hi)
                seen = high.get(piece.base.epoch)
                if seen is not None and entry.end_reading <= seen:
                    continue  # the whole range was already allocated
                if seen is not None and entry.start_reading < seen:
                    entry.start_reading, entry.hours = seen, entry.end_reading - seen
                high[piece.base.epoch] = entry.end_reading
                entries.append(entry)
            offset = top
    return Plan(entries, dict(totals))
