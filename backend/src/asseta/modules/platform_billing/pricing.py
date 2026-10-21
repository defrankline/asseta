"""Pure invoice and proration computation. All money is Decimal and quantized to currency minor units
with the rate version's rounding mode. No I/O here: services supply inputs, persist outputs."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from asseta.core.money import RoundingMode, quantize
from asseta.modules.platform_billing.calendar import Period
from asseta.modules.platform_billing.enums import InvoiceLineType, MidCycleAddPolicy, MidCycleRemovePolicy

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class RateTerms:
    unit_price: Decimal
    minimum_billable_assets: int
    discount_percent: Decimal
    tax_name: str | None
    tax_rate_percent: Decimal
    minor_units: int
    rounding: RoundingMode
    mid_cycle_add: MidCycleAddPolicy
    mid_cycle_remove: MidCycleRemovePolicy

    def q(self, amount: Decimal) -> Decimal:
        return quantize(amount, self.minor_units, self.rounding)


@dataclass(frozen=True)
class EnrolledAsset:
    machine_id: uuid.UUID
    label: str


@dataclass(frozen=True)
class PendingChargeInput:
    pending_charge_id: uuid.UUID
    line_type: InvoiceLineType
    amount: Decimal
    description: str
    service_from: date
    service_to: date


@dataclass(frozen=True)
class ComputedLine:
    line_type: InvoiceLineType
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    machine_id: uuid.UUID | None = None
    service_from: date | None = None
    service_to: date | None = None
    pending_charge_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ComputedInvoice:
    lines: list[ComputedLine]
    enrolled_assets: int
    billable_assets: int
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal


def compute_invoice(
    terms: RateTerms,
    period: Period,
    assets: list[EnrolledAsset],
    pending: list[PendingChargeInput],
    cadence_label: str,
) -> ComputedInvoice:
    unique = {a.machine_id: a for a in assets}  # distinct machines only, defensively
    ordered = sorted(unique.values(), key=lambda a: a.label)
    unit = terms.q(terms.unit_price)
    lines = [
        ComputedLine(
            InvoiceLineType.ASSET_SUBSCRIPTION,
            f"{a.label} — {cadence_label} subscription",
            Decimal(1),
            unit,
            unit,
            a.machine_id,
            period.start,
            period.end,
        )
        for a in ordered
    ]
    shortfall = terms.minimum_billable_assets - len(ordered)
    if shortfall > 0:
        lines.append(
            ComputedLine(
                InvoiceLineType.MINIMUM_COMMITMENT,
                f"Minimum commitment: {terms.minimum_billable_assets} assets ({len(ordered)} enrolled)",
                Decimal(shortfall),
                unit,
                terms.q(unit * shortfall),
                None,
                period.start,
                period.end,
            )
        )
    for p in sorted(pending, key=lambda x: (x.service_from, str(x.pending_charge_id))):
        lines.append(
            ComputedLine(
                p.line_type,
                p.description,
                Decimal(1),
                p.amount,
                p.amount,
                None,
                p.service_from,
                p.service_to,
                p.pending_charge_id,
            )
        )
    subtotal = sum((line.amount for line in lines), Decimal(0))
    discount = terms.q(subtotal * terms.discount_percent / HUNDRED)
    if discount:
        lines.append(
            ComputedLine(
                InvoiceLineType.DISCOUNT,
                f"Negotiated discount {terms.discount_percent}%",
                Decimal(1),
                -discount,
                -discount,
            )
        )
    tax = terms.q((subtotal - discount) * terms.tax_rate_percent / HUNDRED)
    if tax:
        lines.append(
            ComputedLine(
                InvoiceLineType.TAX, f"{terms.tax_name or 'Tax'} {terms.tax_rate_percent}%", Decimal(1), tax, tax
            )
        )
    return ComputedInvoice(
        lines,
        len(ordered),
        max(len(ordered), terms.minimum_billable_assets),
        subtotal,
        discount,
        tax,
        subtotal - discount + tax,
    )


@dataclass(frozen=True)
class ProrationResult:
    line_type: InvoiceLineType
    days: int
    amount: Decimal
    explanation: str


def prorate_add(terms: RateTerms, period: Period, effective: date, active_before: int) -> ProrationResult:
    days = (period.end - effective).days
    kind = InvoiceLineType.PRORATION_CHARGE
    if active_before < terms.minimum_billable_assets:
        return ProrationResult(
            kind,
            days,
            Decimal(0),
            f"Covered by minimum commitment ({active_before + 1} of {terms.minimum_billable_assets} assets)",
        )
    if terms.mid_cycle_add is MidCycleAddPolicy.NEXT_PERIOD:
        return ProrationResult(kind, days, Decimal(0), "Policy NEXT_PERIOD: billed from next period")
    if terms.mid_cycle_add is MidCycleAddPolicy.FULL_PERIOD:
        return ProrationResult(kind, period.days, terms.q(terms.unit_price), "Policy FULL_PERIOD: full period charge")
    amount = terms.q(terms.unit_price * days / period.days)
    return ProrationResult(kind, days, amount, f"Policy PRORATE_DAILY: {days}/{period.days} days")


def prorate_remove(terms: RateTerms, period: Period, effective: date, active_after: int) -> ProrationResult:
    days = (period.end - effective).days
    kind = InvoiceLineType.PRORATION_CREDIT
    if active_after < terms.minimum_billable_assets:
        return ProrationResult(
            kind,
            days,
            Decimal(0),
            f"No credit: fleet at/below minimum commitment ({active_after} of {terms.minimum_billable_assets} assets)",
        )
    if terms.mid_cycle_remove is MidCycleRemovePolicy.NO_CREDIT:
        return ProrationResult(kind, days, Decimal(0), "Policy NO_CREDIT: no credit for remaining days")
    amount = -terms.q(terms.unit_price * days / period.days)
    return ProrationResult(kind, days, amount, f"Policy PRORATE_CREDIT: {days}/{period.days} days")
