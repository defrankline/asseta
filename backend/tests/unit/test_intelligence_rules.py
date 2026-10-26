"""Gate 6 pure risk rules: each fires with fact/threshold evidence and stays silent at the boundary."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from asseta.modules.intelligence.models import RuleCode, SignalSeverity, SubjectType
from asseta.modules.intelligence.rules import (
    CustodyPosition,
    EngineDay,
    EngineHoursSample,
    EngineState,
    FuelWindow,
    JobWindow,
    MachineFuelPeriod,
    MachineWeekSpend,
    MeterGap,
    MovementAlert,
    ReceiptUse,
    TrackerGap,
    WorkRecord,
    cash_not_handed_over,
    duplicate_receipts,
    engine_running_without_work,
    expense_threshold_exceeded,
    fuel_allowance_exceeded,
    machine_fuel_above_norm,
    runs_from_engine_hours,
    runs_from_states,
    uncovered,
    unreported_engine_activity,
    work_without_authorization,
)
from asseta.modules.policy.schemas import SEED_DEFAULTS, FraudControlsPolicy, PolicyType

T0 = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
M = uuid.uuid4()
PV = "FRAUD_CONTROLS@P1"


def h(hours: float) -> datetime:
    return T0 + timedelta(hours=hours)


def test_seed_defaults_validate_and_rules_are_off_by_default() -> None:
    p = FraudControlsPolicy.model_validate(SEED_DEFAULTS[PolicyType.FRAUD_CONTROLS])
    assert p.fuel_max_litres_per_meter_hour is None and p.expense_threshold_per_machine_per_week is None
    assert p.engine_without_work_case_min_minutes is None and p.fuel_check_period is None
    assert p.fuel_litres_per_hour_max is None


def test_engine_runs_from_states_and_uncovered_segments() -> None:
    runs = runs_from_states([EngineState(h(0), True), EngineState(h(2), False), EngineState(h(3), True)], h(4))
    assert [(r.start, r.end, r.ongoing) for r in runs] == [(h(0), h(2), False), (h(3), h(4), True)]
    job = JobWindow(uuid.uuid4(), "J-1", h(1), h(1.5))
    assert uncovered(h(0), h(2), [job]) == [(h(0), h(1)), (h(1.5), h(2))]
    assert uncovered(h(0), h(2), [JobWindow(uuid.uuid4(), "J-2", h(-1), None)]) == []


def test_unreported_engine_activity_threshold_boundary_and_verification() -> None:
    runs = runs_from_states([EngineState(h(0), True), EngineState(h(0.5), False)], h(1))
    [f] = unreported_engine_activity(M, runs, [], h(-10), 30, PV)
    assert f.rule_code is RuleCode.UNREPORTED_ENGINE_ACTIVITY and f.subject_type is SubjectType.MACHINE
    assert f.evidence["uncovered_minutes"] == 30.0 and f.evidence["threshold_minutes"] == 30
    assert unreported_engine_activity(M, runs, [], h(-10), 31, PV) == []  # just under the threshold
    assert unreported_engine_activity(M, runs, [], h(0.2), 30, PV) == []  # only verified time counts
    covered = [JobWindow(uuid.uuid4(), "J-1", h(-1), None)]
    assert unreported_engine_activity(M, runs, covered, h(-10), 30, PV) == []


def test_engine_hours_runs_skip_runs_started_before_window() -> None:
    samples = [EngineHoursSample(h(i), Decimal(v)) for i, v in enumerate(["10", "11", "12", "12", "13", "14"])]
    runs = runs_from_engine_hours(samples, h(0.5))
    assert [(r.start, r.end) for r in runs] == [(h(3), h(5))]
    assert runs[0].detail["engine_hours_start"] == "12"


def _use(sha: str, submitted_h: float, incurred_h: float) -> ReceiptUse:
    return ReceiptUse(
        uuid.uuid4(), sha, h(incurred_h), h(submitted_h), uuid.uuid4(), None, M, None, Decimal("50000"), "TZS"
    )


def test_duplicate_receipt_reports_later_expense_within_lookback() -> None:
    a, b, c = _use("abc", 0, 0), _use("abc", 1, 24 * 5), _use("zzz", 2, 0)
    [f] = duplicate_receipts([a, b, c], 5, PV)
    assert f.subject_id == b.expense_id and f.evidence["same_receipt_on"][0]["expense_id"] == str(a.expense_id)
    assert set(f.involved_user_ids) == {a.submitted_by, b.submitted_by}
    assert duplicate_receipts([a, b], 4, PV) == []  # 5 days apart, lookback 4
    assert duplicate_receipts([a, b], 5, PV, candidates={a.expense_id}) == []


def _fuel(into: str, used: str, opening: str = "100", closing: str = "110") -> FuelWindow:
    return FuelWindow(
        M, uuid.uuid4(), "J-1", Decimal(opening), Decimal(closing), h(0), h(10), Decimal(into), Decimal(used), (), ()
    )


def test_fuel_allowance_boundary_and_unknown_hours() -> None:
    f = fuel_allowance_exceeded(_fuel("150.5", "10"), Decimal("15"), PV)
    assert f is not None and f.evidence["litres_per_meter_hour"] == "15.050"
    assert fuel_allowance_exceeded(_fuel("150", "150"), Decimal("15"), PV) is None  # exactly at the allowance
    assert fuel_allowance_exceeded(_fuel("500", "0", "100", "100"), Decimal("15"), PV) is None  # hours unknown
    assert fuel_allowance_exceeded(_fuel("500", "0"), None, PV) is None  # rule off


def test_expense_threshold_boundary() -> None:
    spend = MachineWeekSpend(M, 2026, 45, h(0), h(24 * 7), "TZS", Decimal("100000"), (uuid.uuid4(),), ())
    assert expense_threshold_exceeded(spend, Decimal("100000"), PV) is None
    f = expense_threshold_exceeded(spend, Decimal("99999.99"), PV)
    assert f is not None and f.dedupe_key == f"EXPW:{M}:2026-W45"


def test_cash_not_handed_over_per_limit() -> None:
    staff = uuid.uuid4()
    pos = CustodyPosition(staff, None, "TZS", Decimal("500000"), h(0), h(48))
    assert cash_not_handed_over(pos, 48, None, PV) == []  # exactly at the age limit
    [old] = cash_not_handed_over(pos, 47, None, PV)
    assert old.severity is SignalSeverity.WARNING and old.evidence["limit"] == "HELD_LONGER_THAN_LIMIT"
    both = cash_not_handed_over(pos, 47, Decimal("100000"), PV)
    assert {f.evidence["limit"] for f in both} == {"HELD_LONGER_THAN_LIMIT", "ABOVE_AMOUNT_LIMIT"}
    assert len({f.dedupe_key for f in both}) == 2


def _work(occurred: float, approved: float | None, completed: float | None, assigned: bool | None) -> WorkRecord:
    return WorkRecord(
        "EXPENSE",
        uuid.uuid4(),
        uuid.uuid4(),
        "J-1",
        M,
        h(occurred),
        h(occurred + 1),
        "APPROVED",
        h(approved) if approved is not None else None,
        h(completed) if completed is not None else None,
        uuid.uuid4(),
        uuid.uuid4() if assigned is not None else None,
        assigned,
    )


def test_work_without_authorization_reasons_and_tolerance() -> None:
    assert work_without_authorization(_work(1, 0, None, True), 5, PV) is None
    assert work_without_authorization(_work(-0.05, 0, None, None), 5, PV) is None  # 3 min early: within tolerance
    f = work_without_authorization(_work(-1, 0, None, None), 5, PV)
    assert f is not None and f.evidence["reasons"] == ["BEFORE_JOB_AUTHORIZED"]
    f = work_without_authorization(_work(5, None, None, False), 5, PV)
    assert f is not None and f.evidence["reasons"] == ["BEFORE_JOB_AUTHORIZED", "SUPERVISOR_NOT_ASSIGNED_TO_MACHINE"]
    f = work_without_authorization(_work(5, 0, 2, None), 5, PV)
    assert f is not None and f.evidence["reasons"] == ["AFTER_JOB_COMPLETED"]


def test_no_finding_text_mentions_fraud() -> None:
    texts = [
        str(f.evidence)
        for f in [
            *duplicate_receipts([_use("abc", 0, 0), _use("abc", 1, 1)], 5, PV),
            *cash_not_handed_over(CustodyPosition(M, None, "TZS", Decimal(1), h(0), h(99)), 1, None, PV),
        ]
    ]
    assert texts and not any("fraud" in t.lower() for t in texts)


def test_engine_running_without_work_takes_the_larger_source_never_the_sum() -> None:
    gap = MeterGap(uuid.uuid4(), uuid.uuid4(), h(0), h(4), Decimal(100), Decimal(102), Decimal(2), Decimal("0.5"))
    day = EngineDay(
        M,
        T0.date(),
        h(-8),
        h(16),
        tracker=(TrackerGap(h(1), h(1.5), "IGNITION"),),  # 30 min
        meter=(gap,),  # 0.5 h = 30 min of the day
        movements=(MovementAlert(uuid.uuid4(), h(12), "Moving after hours"),),
    )
    assert engine_running_without_work(day, None, PV) is None  # off
    assert engine_running_without_work(day, 31, PV) is None  # 30 + 30 never adds up to 60
    f = engine_running_without_work(day, 30, PV)
    assert f is not None and f.rule_code is RuleCode.ENGINE_RUNNING_WITHOUT_WORK
    assert f.dedupe_key == f"EWW:{M}:{T0.date().isoformat()}" and f.subject_type is SubjectType.MACHINE
    ev = f.evidence
    assert (ev["minutes_without_work"], ev["tracker_minutes_without_job"], ev["meter_unexplained_hours"]) == (
        30.0,
        30.0,
        "0.50",
    )
    assert ev["after_hours_movements"] == 1 and ev["threshold_minutes"] == 30


def test_machine_fuel_above_norm_boundary_and_zero_hours() -> None:
    p = MachineFuelPeriod(
        M, "WEEK", "2026-W45", h(0), h(168), Decimal(50), Decimal(10), Decimal(6), (uuid.uuid4(),), (), ("J-1",)
    )
    assert machine_fuel_above_norm(p, None, "TENANT", PV) is None  # off
    assert machine_fuel_above_norm(p, Decimal(5), "TENANT", PV) is None  # exactly at the norm
    f = machine_fuel_above_norm(p, Decimal("4.9"), "MACHINE_CATEGORY", PV)
    assert f is not None and f.rule_code is RuleCode.MACHINE_FUEL_ABOVE_NORM
    assert f.dedupe_key == f"MFUEL:{M}:2026-W45" and f.evidence["litres_per_engine_hour"] == "5.000"
    assert (f.evidence["engine_hours_in_jobs"], f.evidence["engine_hours_outside_jobs"]) == ("6.00", "4.00")
    assert f.evidence["norm_source"] == "MACHINE_CATEGORY" and f.evidence["job_numbers"] == ["J-1"]
    idle = MachineFuelPeriod(M, "DAY", "2026-11-02", h(0), h(24), Decimal(50), Decimal(0), Decimal(0), (), ())
    assert machine_fuel_above_norm(idle, Decimal(1), "TENANT", PV) is None  # no engine hours: not judged
