"""Pure hire-charge computation from a job's owner-approved terms and its contract-rule billable hours.

This is the single source of truth for what a completed job is worth: the job summary exposes it and tenant hire
invoices snapshot it verbatim (R1-G). Amounts are rounded per line to the currency's minor units (HALF_UP).
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from asseta.core.money import quantize
from asseta.modules.jobs.models import Job, StandbyTreatment

HUNDRED = Decimal(100)


def _plain(v: Decimal) -> str:
    """Hours and percentages without storage padding: 11.500000 -> 11.5, 18.0000 -> 18."""
    return format(v.normalize(), "f")


class ChargeKind(StrEnum):
    HIRE = "HIRE"
    STANDBY = "STANDBY"
    MOBILIZATION = "MOBILIZATION"
    DISCOUNT = "DISCOUNT"
    TAX = "TAX"


@dataclass(frozen=True)
class ChargeLine:
    kind: ChargeKind
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal  # DISCOUNT lines are negative


@dataclass(frozen=True)
class JobCharges:
    currency: str
    lines: tuple[ChargeLine, ...]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal


def job_charges(job: Job, billable_hours: Decimal, standby_hours: Decimal, minor_units: int) -> JobCharges:
    def q(v: Decimal) -> Decimal:
        return quantize(v, minor_units)

    def money(v: Decimal) -> str:
        return f"{job.currency} {q(v):,}"

    lines = [
        ChargeLine(
            ChargeKind.HIRE,
            f"Hire {job.job_number}: {_plain(billable_hours)} h @ {money(job.hourly_rate)}/h",
            billable_hours,
            job.hourly_rate,
            q(billable_hours * job.hourly_rate),
        )
    ]
    if job.standby_treatment is StandbyTreatment.STANDBY_RATE and job.standby_rate is not None and standby_hours > 0:
        lines.append(
            ChargeLine(
                ChargeKind.STANDBY,
                f"Standby {job.job_number}: {_plain(standby_hours)} h @ {money(job.standby_rate)}/h",
                standby_hours,
                job.standby_rate,
                q(standby_hours * job.standby_rate),
            )
        )
    if job.mobilization_fee > 0:
        lines.append(
            ChargeLine(
                ChargeKind.MOBILIZATION,
                f"Mobilization {job.job_number}",
                Decimal(1),
                job.mobilization_fee,
                q(job.mobilization_fee),
            )
        )
    subtotal = sum((line.amount for line in lines), Decimal(0))
    discount = q(subtotal * job.discount_percent / HUNDRED)
    if discount > 0:
        lines.append(
            ChargeLine(
                ChargeKind.DISCOUNT, f"Discount {_plain(job.discount_percent)}%", Decimal(1), -discount, -discount
            )
        )
    tax = q((subtotal - discount) * job.tax_rate_percent / HUNDRED)
    if tax > 0:
        lines.append(ChargeLine(ChargeKind.TAX, f"Tax {_plain(job.tax_rate_percent)}%", Decimal(1), tax, tax))
    return JobCharges(job.currency, tuple(lines), subtotal, discount, tax, subtotal - discount + tax)
