"""Machine engine-hour ledger (design B, [3.2.3]-[3.2.6]) as a pure, deterministic function of plain facts.

Consecutive meter points of one machine (the approved baseline, then its live readings in capture-time order) form
intervals; each interval's elapsed engine hours come from the two readings (an approved meter reset in between
re-bases the count). An interval inside a started job's opening->closing window is CUSTOMER_WORK; anything else is
UNALLOCATED and carries a classification: UNEXPLAINED until a person's explanation (APPROVED_NON_CUSTOMER with a
tenant category, or IDENTIFIED_VARIANCE with a tenant reason) is approved. Time alone never changes a
classification. When the tenant's revenue-hour basis is on (DEC-031 R1), non-billable work-log time of the job's
declared non-revenue types (e.g. MOBILIZATION) inside a customer-work interval is its own NON_REVENUE bucket.
Nothing here is stored: the ledger is re-derived from immutable readings on every read, so it is always
reproducible from its sources ([3.4.6], [3.4.7])."""

import itertools
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum

ZERO = Decimal(0)
HOUR_STEP = Decimal("0.01")


class SegmentKind(StrEnum):
    CUSTOMER_WORK = "CUSTOMER_WORK"
    UNALLOCATED = "UNALLOCATED"
    NON_REVENUE = "NON_REVENUE"  # non-revenue work-log time inside a job window (revenue-hour basis, DEC-031 R1)


class SegmentClassification(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"  # customer work, or an unallocated interval with no engine hours
    UNEXPLAINED = "UNEXPLAINED"
    APPROVED_NON_CUSTOMER = "APPROVED_NON_CUSTOMER"
    IDENTIFIED_VARIANCE = "IDENTIFIED_VARIANCE"


class ReadingReview(StrEnum):
    VERIFIED = "VERIFIED"  # both boundary readings accepted (or their blocking findings reviewed)
    PENDING_REVIEW = "PENDING_REVIEW"  # a boundary reading still has an unreviewed blocking finding


@dataclass(frozen=True)
class LedgerPoint:
    ref: uuid.UUID  # meter capture id, or the baseline id
    source: str  # "BASELINE" or the reading kind (OPENING / CLOSING / DAILY)
    at: datetime
    reading: Decimal
    known_at: datetime  # when the server learned of the point (receipt / baseline approval)
    verified: bool
    job_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ResetPoint:
    effective_at: datetime
    old_reading: Decimal
    new_reading: Decimal


@dataclass(frozen=True)
class JobSpan:
    """A started job's engine window: opening reading time -> closing reading time (open while running)."""

    job_id: uuid.UUID
    job_number: str
    start: datetime
    end: datetime | None
    start_reading: Decimal
    end_reading: Decimal | None
    customer_id: uuid.UUID | None = None
    requires_cover: bool = False  # DEC-032 A2: in-job hours need a covering work-log entry (policy at job start)
    splits_billing: bool = False  # DEC-032 A3: hours after a changeover leave this job's billing (policy at job start)


@dataclass(frozen=True)
class ChangeoverPoint:
    """DEC-032 A3: a mid-job changeover reading: from `at` on, this job's hours serve `to_customer_id`."""

    id: uuid.UUID
    at: datetime
    job_id: uuid.UUID
    to_customer_id: uuid.UUID
    to_job_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ActivitySpan:
    """A non-billable work-log entry of a declared non-revenue type (wall-clock window) on one job."""

    job_id: uuid.UUID
    activity_type: str
    start: datetime
    end: datetime
    approval_id: uuid.UUID | None = None  # the second person's approval, when the tenant requires one


@dataclass(frozen=True)
class ClassificationFact:
    id: uuid.UUID
    start_ref: uuid.UUID
    end_ref: uuid.UUID
    hours: Decimal
    status: str  # PROPOSED | APPROVED
    outcome: str
    reason_id: uuid.UUID


@dataclass
class LedgerInterval:
    start: LedgerPoint
    end: LedgerPoint
    hours: Decimal  # elapsed engine hours (never negative; see `inconsistent`)
    raw_hours: Decimal
    reset_applied: bool
    inconsistent: bool  # the meter went backwards without an approved reset (already flagged at capture)
    review: ReadingReview
    kind: SegmentKind
    classification: SegmentClassification
    job_id: uuid.UUID | None = None
    job_number: str | None = None
    overlapping_job_ids: list[uuid.UUID] = field(default_factory=list)
    approved: ClassificationFact | None = None
    proposal: ClassificationFact | None = None
    non_revenue: dict[str, Decimal] = field(default_factory=dict)  # activity type -> engine hours (R1)
    job_customer_id: uuid.UUID | None = None
    in_job_unexplained: Decimal = ZERO  # A2: hours of a job window no work-log entry covers
    changeover_id: uuid.UUID | None = None  # A3: the changeover that moved this interval to another customer
    changeover_customer_id: uuid.UUID | None = None
    # A3, policy on and another customer: the billable hours that move from this job to the named job (never fewer
    # for one than the other gains), and that job. Time the job's billing already deducts stays deducted, not moved.
    changeover_cut: Decimal = ZERO
    billed_to_job_id: uuid.UUID | None = None
    non_revenue_approvals: dict[str, list[uuid.UUID]] = field(default_factory=dict)  # activity type -> approvals

    @property
    def non_revenue_hours(self) -> Decimal:
        return sum(self.non_revenue.values(), ZERO)

    @property
    def customer_work_hours(self) -> Decimal:
        """Customer-work hours after the revenue-hour basis and A2 (0 for unallocated intervals)."""
        if self.kind is not SegmentKind.CUSTOMER_WORK:
            return ZERO
        return self.hours - self.non_revenue_hours - self.in_job_unexplained

    @property
    def explainable_hours(self) -> Decimal:
        """The hours a classification explains: the whole of an unallocated interval, or a job's uncovered part."""
        return self.in_job_unexplained if self.kind is SegmentKind.CUSTOMER_WORK else self.hours

    @property
    def billing_cut(self) -> Decimal:
        """Engine hours of this interval its job does not bill (A2 uncovered, A3 served to another customer)."""
        return self.in_job_unexplained + self.changeover_cut

    @property
    def key(self) -> tuple[uuid.UUID, uuid.UUID]:
        return self.start.ref, self.end.ref

    @property
    def opened_at(self) -> datetime:
        """When the segment became known to the server (ageing starts here, not at the engine time)."""
        return max(self.start.known_at, self.end.known_at)

    @property
    def open_item(self) -> bool:
        """An unallocated, verified interval with hours that nobody has explained yet."""
        return (
            (self.kind is SegmentKind.UNALLOCATED or self.in_job_unexplained > ZERO)
            and self.review is ReadingReview.VERIFIED
            and self.classification is SegmentClassification.UNEXPLAINED
        )


@dataclass
class LedgerTotals:
    total_hours: Decimal = ZERO
    customer_work_hours: Decimal = ZERO
    non_revenue_hours: Decimal = ZERO  # revenue-hour basis (DEC-031 R1); 0 while the tenant has it off
    unallocated_hours: Decimal = ZERO
    approved_non_customer_hours: Decimal = ZERO
    identified_variance_hours: Decimal = ZERO
    unexplained_hours: Decimal = ZERO
    proposed_hours: Decimal = ZERO  # unexplained hours with a classification awaiting approval
    pending_review_hours: Decimal = ZERO  # unallocated hours whose readings still await review


@dataclass(frozen=True)
class JobOverlap:
    first_job_id: uuid.UUID
    second_job_id: uuid.UUID
    basis: str  # TIME or METER_RANGE


@dataclass
class Ledger:
    intervals: list[LedgerInterval]
    overlaps: list[JobOverlap]

    def totals(self, intervals: Sequence[LedgerInterval] | None = None) -> LedgerTotals:
        t = LedgerTotals()
        for i in self.intervals if intervals is None else intervals:
            t.total_hours += i.hours
            if i.kind is SegmentKind.CUSTOMER_WORK:
                t.customer_work_hours += i.customer_work_hours
                t.non_revenue_hours += i.non_revenue_hours
                if i.in_job_unexplained <= ZERO:
                    continue
            hours = i.explainable_hours
            t.unallocated_hours += hours
            if i.review is ReadingReview.PENDING_REVIEW:
                t.pending_review_hours += hours
            elif i.classification is SegmentClassification.APPROVED_NON_CUSTOMER:
                t.approved_non_customer_hours += hours
            elif i.classification is SegmentClassification.IDENTIFIED_VARIANCE:
                t.identified_variance_hours += hours
            elif i.classification is SegmentClassification.UNEXPLAINED:
                t.unexplained_hours += hours
                if i.proposal is not None:
                    t.proposed_hours += hours
        return t


def elapsed_hours(start: LedgerPoint, end: LedgerPoint, resets: Sequence[ResetPoint]) -> tuple[Decimal, bool]:
    """Meter hours between two points; approved resets effective in (start, end] re-base the count."""
    between = sorted((r for r in resets if start.at < r.effective_at <= end.at), key=lambda r: r.effective_at)
    current, total = start.reading, ZERO
    for r in between:
        total += r.old_reading - current
        current = r.new_reading
    return total + (end.reading - current), bool(between)


def _covering(spans: Sequence[JobSpan], start: datetime, end: datetime) -> list[JobSpan]:
    return [s for s in spans if s.start <= start and (s.end is None or end <= s.end)]


def rebased_between(resets: Sequence[ResetPoint], a: datetime, b: datetime) -> bool:
    """An approved meter reset between two instants: their readings are on different meter bases."""
    lo, hi = min(a, b), max(a, b)
    return any(lo < r.effective_at <= hi for r in resets)


def job_overlaps(spans: Sequence[JobSpan], resets: Sequence[ResetPoint] = ()) -> list[JobOverlap]:
    """Pairs of started jobs on one machine whose windows overlap in time or in meter range (no engine hour may
    be allocated twice, [3.2.5]). Meter ranges are only compared on the same meter base (no reset between)."""
    out: list[JobOverlap] = []
    ordered = sorted(spans, key=lambda s: (s.start, str(s.job_id)))
    for a, b in itertools.combinations(ordered, 2):
        a_end = a.end if a.end is not None else datetime.max.replace(tzinfo=a.start.tzinfo)
        b_end = b.end if b.end is not None else datetime.max.replace(tzinfo=b.start.tzinfo)
        if a.start < b_end and b.start < a_end:
            out.append(JobOverlap(a.job_id, b.job_id, "TIME"))
            continue
        if (
            a.end_reading is not None
            and b.end_reading is not None
            and a.start_reading < b.end_reading
            and b.start_reading < a.end_reading
            and not rebased_between(resets, a.start, b.start)
        ):
            out.append(JobOverlap(a.job_id, b.job_id, "METER_RANGE"))
    return out


def non_revenue_split(
    hours: Decimal, start: datetime, end: datetime, job_id: uuid.UUID, activities: Sequence[ActivitySpan]
) -> dict[str, Decimal]:
    """Engine hours of a customer-work interval that belong to its job's non-revenue activities: the wall-clock
    overlap of each type with the interval (the engine is taken to run while moving/standing by), never more than
    the interval's engine hours (scaled down proportionally), rounded down to 0.01 h."""
    seconds: dict[str, float] = {}
    for a in activities:
        if a.job_id != job_id:
            continue
        overlap = (min(a.end, end) - max(a.start, start)).total_seconds()
        if overlap > 0:
            seconds[a.activity_type] = seconds.get(a.activity_type, 0.0) + overlap
    if not seconds or hours <= ZERO:
        return {}
    raw = {t: Decimal(str(v)) / Decimal(3600) for t, v in seconds.items()}
    total = sum(raw.values(), ZERO)
    scale = min(Decimal(1), hours / total)
    out = {t: (v * scale).quantize(HOUR_STEP, rounding=ROUND_DOWN) for t, v in sorted(raw.items())}
    return {t: v for t, v in out.items() if v > ZERO}


def uncovered_hours(
    hours: Decimal, start: datetime, end: datetime, job_id: uuid.UUID, cover: Sequence[ActivitySpan]
) -> Decimal:
    """DEC-032 A2: engine hours of a job interval with no work-log entry over them, by wall-clock share of the union
    of the job's timed entries. A zero-length interval counts as covered."""
    total = (end - start).total_seconds()
    if hours <= ZERO or total <= 0:
        return ZERO
    windows = sorted(
        (max(c.start, start), min(c.end, end)) for c in cover if c.job_id == job_id and c.end > start and c.start < end
    )
    covered, reach = 0.0, start
    for lo, hi in windows:
        lo = max(lo, reach)
        if hi > lo:
            covered += (hi - lo).total_seconds()
            reach = hi
    share = Decimal(str(covered)) / Decimal(str(total))
    return max(hours - (hours * share).quantize(HOUR_STEP, rounding=ROUND_DOWN), ZERO)


def _apply_changeover(
    interval: LedgerInterval,
    job: JobSpan,
    changeovers: Sequence[ChangeoverPoint],
    billing_spans: Sequence[ActivitySpan],
) -> None:
    """DEC-032 A3: the latest changeover of the job at or before this interval decides which customer it served. With
    the tenant's switch on, the interval's billable hours move to the named job: what this job loses that job gains."""
    latest = max(
        (c for c in changeovers if c.job_id == job.job_id and c.at <= interval.start.at),
        key=lambda c: (c.at, str(c.id)),
        default=None,
    )
    if latest is None:
        return
    interval.changeover_id, interval.changeover_customer_id = latest.id, latest.to_customer_id
    if not job.splits_billing or latest.to_customer_id == job.customer_id or latest.to_job_id is None:
        return
    deducted = sum(
        non_revenue_split(interval.hours, interval.start.at, interval.end.at, job.job_id, billing_spans).values(), ZERO
    )
    interval.billed_to_job_id = latest.to_job_id
    interval.changeover_cut = max(interval.hours - interval.in_job_unexplained - deducted, ZERO)


def _approvals(
    a: datetime, b: datetime, job_id: uuid.UUID, spans: Sequence[ActivitySpan]
) -> dict[str, list[uuid.UUID]]:
    """The approvals behind an interval's non-revenue time, per work-log type (DEC-032 A1 approval reference)."""
    out: dict[str, set[uuid.UUID]] = {}
    for s in spans:
        if s.job_id == job_id and s.approval_id is not None and s.end > a and s.start < b:
            out.setdefault(s.activity_type, set()).add(s.approval_id)
    return {t: sorted(ids, key=str) for t, ids in out.items()}


def build_ledger(
    points: Sequence[LedgerPoint],
    resets: Sequence[ResetPoint],
    spans: Sequence[JobSpan],
    classifications: Sequence[ClassificationFact],
    non_revenue: Sequence[ActivitySpan] = (),
    cover: Sequence[ActivitySpan] = (),
    changeovers: Sequence[ChangeoverPoint] = (),
    billing_spans: Sequence[ActivitySpan] = (),
) -> Ledger:
    ordered = sorted(points, key=lambda p: (p.at, p.reading, 0 if p.source == "BASELINE" else 1, str(p.ref)))
    by_key: dict[tuple[uuid.UUID, uuid.UUID], list[ClassificationFact]] = {}
    for c in classifications:
        by_key.setdefault((c.start_ref, c.end_ref), []).append(c)
    intervals: list[LedgerInterval] = []
    for a, b in itertools.pairwise(ordered):
        raw, reset_applied = elapsed_hours(a, b, resets)
        hours = raw if raw > ZERO else ZERO
        review = ReadingReview.VERIFIED if a.verified and b.verified else ReadingReview.PENDING_REVIEW
        covering = _covering(spans, a.at, b.at)
        interval = LedgerInterval(
            start=a,
            end=b,
            hours=hours,
            raw_hours=raw,
            reset_applied=reset_applied,
            inconsistent=raw < ZERO,
            review=review,
            kind=SegmentKind.CUSTOMER_WORK if covering else SegmentKind.UNALLOCATED,
            classification=SegmentClassification.NOT_APPLICABLE,
        )
        if covering:
            first = min(covering, key=lambda s: (s.start, str(s.job_id)))  # one job only: never counted twice
            interval.job_id, interval.job_number = first.job_id, first.job_number
            interval.overlapping_job_ids = [s.job_id for s in covering if s.job_id != first.job_id]
            interval.job_customer_id = first.customer_id
            if non_revenue:
                interval.non_revenue = non_revenue_split(hours, a.at, b.at, first.job_id, non_revenue)
                interval.non_revenue_approvals = _approvals(a.at, b.at, first.job_id, non_revenue)
            if first.requires_cover:
                uncovered = uncovered_hours(hours, a.at, b.at, first.job_id, cover)
                interval.in_job_unexplained = min(uncovered, hours - interval.non_revenue_hours)
            _apply_changeover(interval, first, changeovers, billing_spans)
        if interval.explainable_hours > ZERO:
            interval.classification = SegmentClassification.UNEXPLAINED
            for c in by_key.get(interval.key, []):
                if c.hours != interval.explainable_hours:
                    continue  # explanation of different hours (boundaries re-based): never stretched over these
                if c.status == "APPROVED":
                    interval.approved = c
                    interval.classification = SegmentClassification(c.outcome)
                elif c.status == "PROPOSED":
                    interval.proposal = c
        intervals.append(interval)
    return Ledger(intervals, job_overlaps(spans, resets))
