from datetime import date

import pytest

from asseta.modules.platform_billing.calendar import add_months, nth_period, period_containing
from asseta.modules.platform_billing.enums import Cadence


def test_add_months_clamps_to_month_end_and_restores_anchor() -> None:
    assert add_months(date(2026, 1, 31), 1, 31) == date(2026, 2, 28)
    assert add_months(date(2026, 1, 31), 2, 31) == date(2026, 3, 31)
    assert add_months(date(2028, 1, 31), 1, 31) == date(2028, 2, 29)
    assert add_months(date(2026, 11, 15), 3, 15) == date(2027, 2, 15)


def test_monthly_periods_are_contiguous() -> None:
    start = date(2026, 1, 31)
    prev = nth_period(start, 31, Cadence.MONTHLY, 0)
    for n in range(1, 30):
        p = nth_period(start, 31, Cadence.MONTHLY, n)
        assert p.start == prev.end
        prev = p


def test_yearly_period_and_containment() -> None:
    p = period_containing(date(2026, 3, 1), 1, Cadence.YEARLY, date(2027, 2, 28))
    assert (p.start, p.end, p.days) == (date(2026, 3, 1), date(2027, 3, 1), 365)
    p2 = period_containing(date(2026, 3, 1), 1, Cadence.YEARLY, date(2027, 3, 1))
    assert p2.start == date(2027, 3, 1)


def test_period_containing_rejects_pre_billing_dates() -> None:
    with pytest.raises(ValueError):
        period_containing(date(2026, 3, 1), 1, Cadence.MONTHLY, date(2026, 2, 28))
