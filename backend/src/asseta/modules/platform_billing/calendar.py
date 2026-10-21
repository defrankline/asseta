"""Billing-period arithmetic. Periods are [start, end) dates anchored to a day of month; months shorter than
the anchor clamp to their last day (e.g. anchor 31 -> Feb 28/29)."""

import calendar as _cal
from dataclasses import dataclass
from datetime import date

from asseta.modules.platform_billing.enums import Cadence


@dataclass(frozen=True)
class Period:
    start: date
    end: date  # exclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def contains(self, d: date) -> bool:
        return self.start <= d < self.end


def add_months(d: date, months: int, anchor_day: int) -> date:
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, min(anchor_day, _cal.monthrange(year, month)[1]))


def months_per_period(cadence: Cadence) -> int:
    return 1 if cadence is Cadence.MONTHLY else 12


def nth_period(billing_start: date, anchor_day: int, cadence: Cadence, n: int) -> Period:
    step = months_per_period(cadence)
    start = billing_start if n == 0 else add_months(billing_start, n * step, anchor_day)
    return Period(start, add_months(billing_start, (n + 1) * step, anchor_day))


def period_index(billing_start: date, anchor_day: int, cadence: Cadence, d: date) -> int:
    if d < billing_start:
        raise ValueError("date precedes billing start")
    step = months_per_period(cadence)
    n = max(0, ((d.year - billing_start.year) * 12 + d.month - billing_start.month) // step - 1)
    while not nth_period(billing_start, anchor_day, cadence, n).contains(d):
        n += 1
    return n


def period_containing(billing_start: date, anchor_day: int, cadence: Cadence, d: date) -> Period:
    return nth_period(billing_start, anchor_day, cadence, period_index(billing_start, anchor_day, cadence, d))
