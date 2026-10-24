"""Engine-hour ledger (design B [3.2.3]-[3.2.6]): pure derivation from readings, job windows and decisions."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from asseta.modules.meter.ledger import (
    ClassificationFact,
    JobSpan,
    LedgerPoint,
    ReadingReview,
    ResetPoint,
    SegmentClassification,
    SegmentKind,
    build_ledger,
    job_overlaps,
)

T0 = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)


def _p(hours: float, reading: str, source: str = "DAILY", verified: bool = True) -> LedgerPoint:
    at = T0 + timedelta(hours=hours)
    return LedgerPoint(uuid.uuid4(), source, at, Decimal(reading), at, verified)


def _span(start: LedgerPoint, end: LedgerPoint | None, number: str = "J-1") -> JobSpan:
    return JobSpan(uuid.uuid4(), number, start.at, end.at if end else None, start.reading, end.reading if end else None)


def test_intervals_split_customer_work_and_unallocated_with_totals() -> None:
    base = _p(0, "1000", "BASELINE")
    daily = _p(3, "1003")
    opening = _p(4, "1003.5", "OPENING")
    mid = _p(6, "1005")
    closing = _p(9, "1008", "CLOSING")
    span = _span(opening, closing)
    ledger = build_ledger([closing, mid, base, opening, daily], [], [span], [])
    kinds = [(i.kind, i.hours) for i in ledger.intervals]
    assert kinds == [
        (SegmentKind.UNALLOCATED, Decimal("3")),
        (SegmentKind.UNALLOCATED, Decimal("0.5")),
        (SegmentKind.CUSTOMER_WORK, Decimal("1.5")),
        (SegmentKind.CUSTOMER_WORK, Decimal("3")),
    ]
    assert ledger.intervals[2].job_id == span.job_id
    t = ledger.totals()
    assert (t.total_hours, t.customer_work_hours, t.unallocated_hours, t.unexplained_hours) == (
        Decimal("8"),
        Decimal("4.5"),
        Decimal("3.5"),
        Decimal("3.5"),
    )
    assert all(i.classification is SegmentClassification.UNEXPLAINED for i in ledger.intervals[:2])


def test_running_job_window_is_open_ended() -> None:
    opening, later = _p(1, "50", "OPENING"), _p(30, "70")
    ledger = build_ledger([opening, later], [], [_span(opening, None)], [])
    assert ledger.intervals[0].kind is SegmentKind.CUSTOMER_WORK


def test_approved_reset_rebases_elapsed_hours_and_decrease_is_inconsistent() -> None:
    a, b = _p(0, "9990"), _p(10, "4")
    reset = ResetPoint(T0 + timedelta(hours=5), Decimal("9995"), Decimal("0"))
    with_reset = build_ledger([a, b], [reset], [], []).intervals[0]
    assert with_reset.hours == Decimal("9") and with_reset.reset_applied
    without = build_ledger([a, b], [], [], []).intervals[0]
    assert without.inconsistent and without.hours == Decimal("0")
    assert without.classification is SegmentClassification.NOT_APPLICABLE  # nothing to explain


def test_classification_matches_exact_segment_and_hours_only() -> None:
    a, b = _p(0, "100"), _p(5, "104")
    approved = ClassificationFact(
        uuid.uuid4(), a.ref, b.ref, Decimal("4"), "APPROVED", "APPROVED_NON_CUSTOMER", uuid.uuid4()
    )
    seg = build_ledger([a, b], [], [], [approved]).intervals[0]
    assert seg.classification is SegmentClassification.APPROVED_NON_CUSTOMER and not seg.open_item
    stale = ClassificationFact(
        uuid.uuid4(), a.ref, b.ref, Decimal("3"), "APPROVED", "IDENTIFIED_VARIANCE", uuid.uuid4()
    )
    seg = build_ledger([a, b], [], [], [stale]).intervals[0]
    assert seg.classification is SegmentClassification.UNEXPLAINED  # never stretched over different hours
    proposed = ClassificationFact(
        uuid.uuid4(), a.ref, b.ref, Decimal("4"), "PROPOSED", "IDENTIFIED_VARIANCE", uuid.uuid4()
    )
    ledger = build_ledger([a, b], [], [], [proposed])
    assert ledger.intervals[0].proposal == proposed and ledger.totals().proposed_hours == Decimal("4")
    # a late reading splitting the segment leaves both halves unexplained
    split = build_ledger([a, _p(2, "101"), b], [], [], [approved]).intervals
    assert [i.classification for i in split] == [SegmentClassification.UNEXPLAINED] * 2


def test_unreviewed_reading_holds_interval_for_review() -> None:
    a, b = _p(0, "10"), _p(2, "12", verified=False)
    seg = build_ledger([a, b], [], [], []).intervals[0]
    assert seg.review is ReadingReview.PENDING_REVIEW and not seg.open_item
    assert build_ledger([a, b], [], [], []).totals().pending_review_hours == Decimal("2")


def test_overlapping_jobs_are_detected_and_hours_counted_once() -> None:
    o1, c1 = _p(0, "100", "OPENING"), _p(8, "108", "CLOSING")
    o2, c2 = _p(4, "104", "OPENING"), _p(10, "110", "CLOSING")
    j1, j2 = _span(o1, c1, "J-1"), _span(o2, c2, "J-2")
    overlaps = job_overlaps([j1, j2])
    assert len(overlaps) == 1 and overlaps[0].basis == "TIME"
    ledger = build_ledger([o1, o2, c1, c2], [], [j1, j2], [])
    covered = [i for i in ledger.intervals if i.overlapping_job_ids]
    assert covered and all(i.job_id == j1.job_id for i in covered)
    assert ledger.totals().total_hours == Decimal("10")  # every engine hour exactly once
    # meter-range overlap without a time overlap (e.g. a back-dated reading)
    o3, c3 = _p(20, "105", "OPENING"), _p(22, "107", "CLOSING")
    assert job_overlaps([j1, _span(o3, c3, "J-3")])[0].basis == "METER_RANGE"
