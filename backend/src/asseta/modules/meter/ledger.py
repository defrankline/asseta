"""Machine engine-hour ledger (design B, [3.2.3]-[3.2.6]) as a pure, deterministic function of plain facts.

Consecutive meter points of one machine (the approved baseline, then its live readings in capture-time order) form
intervals; each interval's elapsed engine hours come from the two readings (an approved meter reset in between
re-bases the count). An interval inside the period of a machine report that is submitted or approved (ADR-008) is
REPORTED: the report accounts for those hours (customers' hours and non-productive reasons). Anything else is
UNALLOCATED and carries a classification: UNEXPLAINED until a person's explanation (APPROVED_NON_CUSTOMER with a
tenant category, or IDENTIFIED_VARIANCE with a tenant reason) is approved. Time alone never changes a
classification. Nothing here is stored: the ledger is re-derived from immutable readings on every read, so it is
always reproducible from its sources ([3.4.6], [3.4.7])."""

import itertools
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

ZERO = Decimal(0)
HOUR_STEP = Decimal("0.01")


class SegmentKind(StrEnum):
    REPORTED = "REPORTED"  # inside a submitted or approved machine report: the report accounts for the hours
    UNALLOCATED = "UNALLOCATED"


class SegmentClassification(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"  # reported hours, or an unallocated interval with no engine hours
    UNEXPLAINED = "UNEXPLAINED"
    APPROVED_NON_CUSTOMER = "APPROVED_NON_CUSTOMER"
    IDENTIFIED_VARIANCE = "IDENTIFIED_VARIANCE"


class ReadingReview(StrEnum):
    VERIFIED = "VERIFIED"  # both boundary readings accepted (or their blocking findings reviewed)
    PENDING_REVIEW = "PENDING_REVIEW"  # a boundary reading still has an unreviewed blocking finding


@dataclass(frozen=True)
class LedgerPoint:
    ref: uuid.UUID  # meter capture id, or the baseline id
    source: str  # "BASELINE" or the reading kind (DAILY)
    at: datetime
    reading: Decimal
    known_at: datetime  # when the server learned of the point (receipt / baseline approval)
    verified: bool


@dataclass(frozen=True)
class ResetPoint:
    effective_at: datetime
    old_reading: Decimal
    new_reading: Decimal


@dataclass(frozen=True)
class ReportSpan:
    """A submitted or approved machine report's period: previous reading time -> its reading's time."""

    report_id: uuid.UUID
    report_number: str
    start: datetime
    end: datetime


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
    report_id: uuid.UUID | None = None
    report_number: str | None = None
    approved: ClassificationFact | None = None
    proposal: ClassificationFact | None = None

    @property
    def reported_hours(self) -> Decimal:
        return self.hours if self.kind is SegmentKind.REPORTED else ZERO

    @property
    def explainable_hours(self) -> Decimal:
        """The hours a classification explains: the whole of an unallocated interval."""
        return self.hours if self.kind is SegmentKind.UNALLOCATED else ZERO

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
            self.kind is SegmentKind.UNALLOCATED
            and self.review is ReadingReview.VERIFIED
            and self.classification is SegmentClassification.UNEXPLAINED
        )


@dataclass
class LedgerTotals:
    total_hours: Decimal = ZERO
    reported_hours: Decimal = ZERO  # inside submitted or approved machine reports
    unallocated_hours: Decimal = ZERO
    approved_non_customer_hours: Decimal = ZERO
    identified_variance_hours: Decimal = ZERO
    unexplained_hours: Decimal = ZERO
    proposed_hours: Decimal = ZERO  # unexplained hours with a classification awaiting approval
    pending_review_hours: Decimal = ZERO  # unallocated hours whose readings still await review


@dataclass
class Ledger:
    intervals: list[LedgerInterval]

    def totals(self, intervals: Sequence[LedgerInterval] | None = None) -> LedgerTotals:
        t = LedgerTotals()
        for i in self.intervals if intervals is None else intervals:
            t.total_hours += i.hours
            if i.kind is SegmentKind.REPORTED:
                t.reported_hours += i.hours
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


def rebased_between(resets: Sequence[ResetPoint], a: datetime, b: datetime) -> bool:
    """An approved meter reset between two instants: their readings are on different meter bases."""
    lo, hi = min(a, b), max(a, b)
    return any(lo < r.effective_at <= hi for r in resets)


def build_ledger(
    points: Sequence[LedgerPoint],
    resets: Sequence[ResetPoint],
    reports: Sequence[ReportSpan],
    classifications: Sequence[ClassificationFact],
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
        covering = min(
            (r for r in reports if r.start <= a.at and b.at <= r.end),
            key=lambda r: (r.start, str(r.report_id)),
            default=None,
        )
        interval = LedgerInterval(
            start=a,
            end=b,
            hours=hours,
            raw_hours=raw,
            reset_applied=reset_applied,
            inconsistent=raw < ZERO,
            review=review,
            kind=SegmentKind.REPORTED if covering is not None else SegmentKind.UNALLOCATED,
            classification=SegmentClassification.NOT_APPLICABLE,
        )
        if covering is not None:
            interval.report_id, interval.report_number = covering.report_id, covering.report_number
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
    return Ledger(intervals)
