"""DEC-031 Phase 1 pure rules: the revenue-hour basis (non-revenue bucket in the ledger), the tenant policy
(tolerances, switched-off behaviour, billing deduction types), expected revenue per window, money attribution and the
reconciliation periods in the tenant's time zone."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from asseta.modules.meter.ledger import ActivitySpan, JobSpan, LedgerPoint, SegmentKind, build_ledger, non_revenue_split
from asseta.modules.policy.revenue import REVENUE_RECONCILIATION_SEED, RevenueReconciliationPolicy
from asseta.modules.revenue.compute import JobTerms, MachineRevenue, MoneyItem, TimeSpan, WorkPiece, job_expected
from asseta.modules.revenue.reconciliation import closed_periods

T0 = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
JOB = uuid.uuid4()
D = Decimal


def _policy(**values: object) -> RevenueReconciliationPolicy:
    return RevenueReconciliationPolicy.model_validate({**REVENUE_RECONCILIATION_SEED, **values})


def _terms(job_id: uuid.UUID = JOB, completed: bool = True, **kw: object) -> JobTerms:
    base: dict[str, object] = {
        "job_id": job_id,
        "job_number": "J-1",
        "customer_id": None,
        "site_id": None,
        "currency": "TZS",
        "hourly_rate": D(100),
        "discount_percent": D(0),
        "standby_rate": None,
        "mobilization_fee": D(0),
        "started_at": T0,
        "completed": completed,
    }
    return JobTerms(**{**base, **kw})  # type: ignore[arg-type]


# --- R1: revenue-hour basis ---------------------------------------------------------------------------------------
def test_non_revenue_split_takes_the_jobs_overlapping_time_capped_at_the_engine_hours() -> None:
    other = uuid.uuid4()
    spans = [
        ActivitySpan(JOB, "MOBILIZATION", T0 - timedelta(hours=1), T0 + timedelta(hours=1)),  # 1 h inside
        ActivitySpan(JOB, "STANDBY", T0 + timedelta(hours=2), T0 + timedelta(hours=2, minutes=30)),
        ActivitySpan(other, "MOBILIZATION", T0, T0 + timedelta(hours=8)),  # another job: never counted
    ]
    assert non_revenue_split(D(8), T0, T0 + timedelta(hours=8), JOB, spans) == {
        "MOBILIZATION": D("1.00"),
        "STANDBY": D("0.50"),
    }
    # More logged time than engine hours: scaled down to the engine hours (never negative customer work).
    long = [ActivitySpan(JOB, "MOBILIZATION", T0, T0 + timedelta(hours=8))]
    assert non_revenue_split(D(2), T0, T0 + timedelta(hours=8), JOB, long) == {"MOBILIZATION": D("2.00")}
    assert non_revenue_split(D(8), T0, T0 + timedelta(hours=8), JOB, []) == {}


def _points() -> list[LedgerPoint]:
    a, b = uuid.uuid4(), uuid.uuid4()
    return [
        LedgerPoint(a, "OPENING", T0, D(1000), T0, True, JOB),
        LedgerPoint(b, "CLOSING", T0 + timedelta(hours=8), D(1008), T0, True, JOB),
    ]


def test_ledger_shows_non_revenue_time_as_its_own_bucket_only_when_given() -> None:
    span = JobSpan(JOB, "J-1", T0, T0 + timedelta(hours=8), D(1000), D(1008))
    mob = [ActivitySpan(JOB, "MOBILIZATION", T0, T0 + timedelta(hours=1))]
    before = build_ledger(_points(), [], [span], [])
    assert before.totals().customer_work_hours == D(8) and before.totals().non_revenue_hours == 0
    after = build_ledger(_points(), [], [span], [], mob)
    [interval] = after.intervals
    assert interval.kind is SegmentKind.CUSTOMER_WORK and interval.non_revenue == {"MOBILIZATION": D("1.00")}
    totals = after.totals()
    assert (totals.total_hours, totals.customer_work_hours, totals.non_revenue_hours) == (D(8), D(7), D(1))


# --- policy -------------------------------------------------------------------------------------------------------
def test_policy_default_is_off_and_switching_off_disables_every_deduction() -> None:
    seed = _policy()
    assert seed.enabled is False and seed.period == "WEEK" and seed.tolerance_percent == 5
    off = _policy(deduct_non_revenue_from_working_hours=True, deduct_non_revenue_from_prepaid_hours=True).in_force()
    assert not off.deduct_non_revenue_from_working_hours and not off.deduct_non_revenue_from_prepaid_hours
    assert off.billing_deductions(prepaid=False) == (["DOWNTIME", "STANDBY"], [])  # today's billing


def test_billing_deductions_follow_the_billing_mode_switches_and_need_approval_by_default() -> None:
    p = _policy(enabled=True, deduct_non_revenue_from_working_hours=True)
    assert p.billing_deductions(prepaid=False) == (["DOWNTIME", "STANDBY"], ["MOBILIZATION"])  # once approved
    assert p.billing_deductions(prepaid=True) == (["DOWNTIME", "STANDBY"], [])
    q = _policy(enabled=True, deduct_non_revenue_from_prepaid_hours=True, non_revenue_requires_approval=False)
    assert q.billing_deductions(prepaid=True) == (["DOWNTIME", "STANDBY", "MOBILIZATION"], [])  # on logging
    assert q.billing_deductions(prepaid=False) == (["DOWNTIME", "STANDBY"], [])


def test_policy_rejects_unknown_or_repeated_activity_types_and_a_tenant_rate_without_amount() -> None:
    with pytest.raises(ValidationError):
        _policy(unexplained_hours_rate_source="TENANT_RATE")
    assert _policy(unexplained_hours_rate_source="TENANT_RATE", unexplained_hours_rate="1000").enabled is False
    with pytest.raises(ValidationError):
        _policy(non_revenue_activity_types=["WORK"])
    with pytest.raises(ValidationError):
        _policy(non_revenue_activity_types=["MOBILIZATION", "MOBILIZATION"])


def test_either_tolerance_exceeded_is_a_difference_and_only_shortfalls_count() -> None:
    p = _policy(enabled=True, tolerance_percent="5")
    assert not p.exceeds_tolerance(D(1000), D(50)) and p.exceeds_tolerance(D(1000), D(51))
    assert not p.exceeds_tolerance(D(1000), D(-500))  # more money than expected: no difference to explain
    q = _policy(enabled=True, tolerance_percent="50", tolerance_amount="10")
    assert q.exceeds_tolerance(D(1000), D(11))  # the amount is exceeded although the percentage is not
    assert not q.exceeds_tolerance(D(1000), D(10))


# --- expected revenue and attribution -----------------------------------------------------------------------------
def test_expected_revenue_splits_hours_by_window_with_standby_fee_and_discount() -> None:
    terms = _terms(standby_rate=D(40), mobilization_fee=D(50), discount_percent=D(10))
    pieces = [WorkPiece(JOB, T0, T0 + timedelta(hours=10), D(10))]
    standby = [TimeSpan(JOB, T0 + timedelta(hours=2), T0 + timedelta(hours=4))]
    whole = job_expected(terms, pieces, standby, None, None)
    assert whole == (D(10) * 100 + D(2) * 40 + 50) * D("0.9")
    first_half = job_expected(terms, pieces, standby, T0, T0 + timedelta(hours=5))
    assert first_half == (D(5) * 100 + D(2) * 40 + 50) * D("0.9")  # fee in the window containing the start
    second_half = job_expected(terms, pieces, standby, T0 + timedelta(hours=5), None)
    assert first_half + second_half == whole


def test_money_is_attributed_in_proportion_and_running_jobs_are_in_progress() -> None:
    done, running = uuid.uuid4(), uuid.uuid4()
    model = MachineRevenue(
        [_terms(done), _terms(running, completed=False)],
        [
            WorkPiece(done, T0, T0 + timedelta(hours=4), D(4)),
            WorkPiece(running, T0 + timedelta(hours=4), T0 + timedelta(hours=6), D(2)),
        ],
        [],
        [MoneyItem(done, "INVOICE_LINE", uuid.uuid4(), uuid.uuid4(), "TZS", D(300))],
    )
    first = model.window(T0, T0 + timedelta(hours=2))["TZS"]
    assert (first.expected, first.attributed, first.in_progress, first.shortfall) == (D(200), D(150), D(0), D(50))
    whole = model.window(None, None)["TZS"]
    assert (whole.expected, whole.in_progress, whole.attributed, whole.shortfall) == (D(600), D(200), D(300), D(100))
    paid_in_full = MachineRevenue(
        [_terms(done)],
        [WorkPiece(done, T0, T0 + timedelta(hours=4), D(4))],
        [],
        [MoneyItem(done, "PREPAID_CONSUMPTION", uuid.uuid4(), uuid.uuid4(), "TZS", D(400), D(4))],
    )
    assert paid_in_full.window(T0, T0 + timedelta(hours=1))["TZS"].shortfall == 0


# --- periods ------------------------------------------------------------------------------------------------------
def test_closed_periods_are_tenant_local_and_bounded_by_the_recheck_window() -> None:
    tz = ZoneInfo("Africa/Dar_es_Salaam")
    now = datetime(2026, 11, 4, 22, 30, tzinfo=UTC)  # Thu 5 Nov 01:30 local: Wed 4 Nov has closed
    days = closed_periods(_policy(enabled=True, period="DAY", recheck_days=2), tz, now)
    assert [p.key for p in days] == ["DAY:2026-11-04", "DAY:2026-11-03"]
    assert days[0].start == datetime(2026, 11, 4, tzinfo=tz) and days[0].end == datetime(2026, 11, 5, tzinfo=tz)
    weeks = closed_periods(_policy(enabled=True, period="WEEK", recheck_days=8), tz, now)
    assert [p.key for p in weeks] == ["WEEK:2026-10-26"]  # the current week (from Mon 2 Nov) is still open
    assert (weeks[0].local_from.isoformat(), weeks[0].local_to.isoformat()) == ("2026-10-26", "2026-11-01")
    assert closed_periods(_policy(enabled=True, period="JOB"), tz, now) == []  # per completed job instead


def test_unexplained_hours_outside_jobs_are_expected_revenue_at_the_chosen_rate() -> None:
    model = MachineRevenue(
        [_terms()],
        [WorkPiece(JOB, T0, T0 + timedelta(hours=4), D(4))],
        [],
        [MoneyItem(JOB, "INVOICE_LINE", uuid.uuid4(), uuid.uuid4(), "TZS", D(400))],
        [TimeSpan(uuid.UUID(int=0), T0 + timedelta(hours=4), T0 + timedelta(hours=6))],
        [D(2)],
        ("TZS", D(50)),
    )
    w = model.window(T0, T0 + timedelta(hours=5))["TZS"]  # half of the unexplained interval
    assert (w.expected, w.unexplained_hours, w.unexplained_expected, w.shortfall) == (D(450), D(1), D(50), D(50))
    assert model.window(None, None, {JOB}, include_unexplained=False)["TZS"].unexplained_hours == 0
    shown_only = MachineRevenue(model.jobs, model.pieces, [], model.money, model.unexplained, [D(2)], None)
    excluded = shown_only.window(None, None)["TZS"]
    assert (excluded.unexplained_hours, excluded.unexplained_expected, excluded.shortfall) == (D(2), D(0), D(0))
