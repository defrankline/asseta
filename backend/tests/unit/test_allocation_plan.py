"""The pure allocation planner (DEC-032 A1): day splitting, meter bases, no double allocation."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D  # noqa: N817
from zoneinfo import ZoneInfo

from asseta.modules.meter.allocation_models import AllocationKind
from asseta.modules.meter.allocation_plan import Plan, plan_allocations
from asseta.modules.meter.ledger import (
    ActivitySpan,
    JobSpan,
    Ledger,
    LedgerPoint,
    ResetPoint,
    build_ledger,
)

T0 = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)
TZ = ZoneInfo("UTC")


def _p(reading: str, hours: float, source: str = "DAILY") -> LedgerPoint:
    return LedgerPoint(uuid.uuid4(), source, T0 + timedelta(hours=hours), D(reading), T0, True)


def _plan(points: list[LedgerPoint], resets: list[ResetPoint] | None = None) -> tuple[Plan, Ledger]:
    ledger = build_ledger(points, resets or [], [], [])
    return plan_allocations(ledger.intervals, resets or [], TZ), ledger


def test_an_interval_over_midnight_splits_by_share_and_ranges_abut() -> None:
    plan, _ = _plan([_p("100", 12), _p("112", 36)])  # 18:00 -> next day 18:00: 6 h before midnight of 24
    entries = plan.entries
    assert [e.work_date.day for e in entries] == [3, 4]
    assert [e.hours for e in entries] == [D("3.00"), D("9.00")]
    assert entries[0].end_reading == entries[1].start_reading == D("103.00")
    assert plan.total_by_day[entries[0].work_date] == D("3.00")


def test_unexplained_interval_outside_a_job_is_one_entry() -> None:
    plan, _ = _plan([_p("100", 0), _p("101", 1)])
    [entry] = plan.entries
    assert entry.kind is AllocationKind.UNEXPLAINED and entry.hours == D(1) and entry.customer_id is None


def test_a_reading_that_went_down_is_never_allocated_twice() -> None:
    plan, _ = _plan([_p("100", 0), _p("110", 2), _p("105", 3), _p("112", 4)])
    # 100-110 allocated; the decrease adds nothing; 105-112 only allocates what is above 110.
    assert [(e.start_reading, e.end_reading) for e in plan.entries] == [(D(100), D(110)), (D(110), D(112))]
    total = sum(plan.total_by_day.values(), D(0))
    assert total == D(17) and sum((e.hours for e in plan.entries), D(0)) == D(12)  # 5 h shown as the difference


def test_an_approved_reset_starts_a_new_meter_base() -> None:
    reset = ResetPoint(T0 + timedelta(hours=3), D(150), D(0))
    plan, _ = _plan([_p("100", 0), _p("150", 2), _p("20", 4)], [reset])
    assert [(e.meter_epoch, e.start_reading, e.end_reading) for e in plan.entries] == [
        (0, D(100), D(150)),
        (1, D(0), D(20)),
    ]


def test_a_job_interval_with_uncovered_time_splits_into_customer_and_unexplained() -> None:
    job = uuid.uuid4()
    a, b = _p("100", 0, "OPENING"), _p("103", 3, "CLOSING")
    span = JobSpan(job, "J", a.at, b.at, a.reading, b.reading, uuid.uuid4(), requires_cover=True)
    cover = [ActivitySpan(job, "WORK", a.at, a.at + timedelta(hours=2))]
    ledger = build_ledger([a, b], [], [span], [], (), cover)
    plan = plan_allocations(ledger.intervals, [], TZ)
    assert [(e.kind, e.hours) for e in plan.entries] == [
        (AllocationKind.CUSTOMER_WORK, D("2.00")),
        (AllocationKind.UNEXPLAINED, D("1.00")),
    ]
    assert plan.entries[1].job_id == job and plan.entries[1].customer_id is None
    t = ledger.totals()
    assert (t.customer_work_hours, t.unexplained_hours, t.unallocated_hours) == (D("2.00"), D("1.00"), D("1.00"))
