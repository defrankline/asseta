"""Gate 6 pure risk rules: each fires with fact/threshold evidence and stays silent at the boundary."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from asseta.modules.intelligence.models import RuleCode, SignalSeverity
from asseta.modules.intelligence.rules import (
    CustodyPosition,
    FuelWindow,
    MachineFuelPeriod,
    MachineWeekSpend,
    ReceiptUse,
    cash_not_handed_over,
    duplicate_receipts,
    expense_threshold_exceeded,
    fuel_allowance_exceeded,
    machine_fuel_above_norm,
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
    assert p.fuel_check_period is None
    assert p.fuel_litres_per_hour_max is None


def _use(sha: str, submitted_h: float, incurred_h: float) -> ReceiptUse:
    return ReceiptUse(uuid.uuid4(), sha, h(incurred_h), h(submitted_h), uuid.uuid4(), None, M, Decimal("50000"), "TZS")


def test_duplicate_receipt_reports_later_expense_within_lookback() -> None:
    a, b, c = _use("abc", 0, 0), _use("abc", 1, 24 * 5), _use("zzz", 2, 0)
    [f] = duplicate_receipts([a, b, c], 5, PV)
    assert f.subject_id == b.expense_id and f.evidence["same_receipt_on"][0]["expense_id"] == str(a.expense_id)
    assert set(f.involved_user_ids) == {a.submitted_by, b.submitted_by}
    assert duplicate_receipts([a, b], 4, PV) == []  # 5 days apart, lookback 4
    assert duplicate_receipts([a, b], 5, PV, candidates={a.expense_id}) == []


def _fuel(into: str, used: str, opening: str = "100", closing: str = "110") -> FuelWindow:
    return FuelWindow(
        M,
        uuid.uuid4(),
        "MR-2026-00001",
        Decimal(opening),
        Decimal(closing),
        h(0),
        h(10),
        Decimal(into),
        Decimal(used),
        (),
        (),
    )


def test_fuel_allowance_boundary_and_unknown_hours() -> None:
    f = fuel_allowance_exceeded(_fuel("150.5", "10"), Decimal("15"), PV)
    assert f is not None and f.evidence["litres_per_meter_hour"] == "15.050"
    assert f.dedupe_key.startswith("FUEL:MR:") and f.evidence["machine_report_number"] == "MR-2026-00001"
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


def test_no_finding_text_mentions_fraud() -> None:
    texts = [
        str(f.evidence)
        for f in [
            *duplicate_receipts([_use("abc", 0, 0), _use("abc", 1, 1)], 5, PV),
            *cash_not_handed_over(CustodyPosition(M, None, "TZS", Decimal(1), h(0), h(99)), 1, None, PV),
        ]
    ]
    assert texts and not any("fraud" in t.lower() for t in texts)


def test_machine_fuel_above_norm_boundary_and_zero_hours() -> None:
    p = MachineFuelPeriod(M, "WEEK", "2026-W45", h(0), h(168), Decimal(50), Decimal(10), (uuid.uuid4(),), ())
    assert machine_fuel_above_norm(p, None, "TENANT", PV) is None  # off
    assert machine_fuel_above_norm(p, Decimal(5), "TENANT", PV) is None  # exactly at the norm
    f = machine_fuel_above_norm(p, Decimal("4.9"), "MACHINE_CATEGORY", PV)
    assert f is not None and f.rule_code is RuleCode.MACHINE_FUEL_ABOVE_NORM
    assert f.dedupe_key == f"MFUEL:{M}:2026-W45" and f.evidence["litres_per_engine_hour"] == "5.000"
    assert f.evidence["engine_hours"] == "10.00" and f.evidence["norm_source"] == "MACHINE_CATEGORY"
    idle = MachineFuelPeriod(M, "DAY", "2026-11-02", h(0), h(24), Decimal(50), Decimal(0), (), ())
    assert machine_fuel_above_norm(idle, Decimal(1), "TENANT", PV) is None  # no engine hours: not judged
