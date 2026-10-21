import uuid
from datetime import date
from decimal import Decimal

from asseta.core.money import RoundingMode
from asseta.modules.platform_billing.calendar import Period
from asseta.modules.platform_billing.enums import InvoiceLineType, MidCycleAddPolicy, MidCycleRemovePolicy
from asseta.modules.platform_billing.pricing import (
    EnrolledAsset,
    PendingChargeInput,
    RateTerms,
    compute_invoice,
    prorate_add,
    prorate_remove,
)

PERIOD = Period(date(2026, 11, 1), date(2026, 12, 1))  # 30 days


def terms(
    price: str = "50000",
    minimum: int = 1,
    discount: str = "0",
    tax: str = "0",
    add: MidCycleAddPolicy = MidCycleAddPolicy.PRORATE_DAILY,
    remove: MidCycleRemovePolicy = MidCycleRemovePolicy.PRORATE_CREDIT,
) -> RateTerms:
    return RateTerms(
        Decimal(price), minimum, Decimal(discount), "VAT", Decimal(tax), 2, RoundingMode.HALF_UP, add, remove
    )


def assets(n: int) -> list[EnrolledAsset]:
    return [EnrolledAsset(uuid.uuid4(), f"EXC-{i:03d}") for i in range(n)]


def test_single_asset_tenant_invoice() -> None:
    inv = compute_invoice(terms("75000.00"), PERIOD, assets(1), [], "Monthly")
    assert inv.total == Decimal("75000.00") and inv.billable_assets == 1
    assert [line.line_type for line in inv.lines] == [InvoiceLineType.ASSET_SUBSCRIPTION]


def test_hundred_assets_with_discount_and_tax_uses_exact_decimals() -> None:
    inv = compute_invoice(terms("33333.33", discount="7.5", tax="18"), PERIOD, assets(100), [], "Monthly")
    assert inv.subtotal == Decimal("3333333.00")
    assert inv.discount_total == Decimal("249999.98")  # 249999.975 -> HALF_UP
    assert inv.tax_total == Decimal("554999.94")  # 3083333.02 * 0.18 = 554999.9436
    assert inv.total == Decimal("3638332.96")
    assert sum(line.amount for line in inv.lines) == inv.total


def test_duplicate_machine_ids_are_billed_once() -> None:
    a = assets(1)[0]
    inv = compute_invoice(terms(), PERIOD, [a, a, a], [], "Monthly")
    assert inv.enrolled_assets == 1 and inv.total == Decimal("50000.00")


def test_minimum_commitment_top_up() -> None:
    inv = compute_invoice(terms("100", minimum=5), PERIOD, assets(2), [], "Monthly")
    assert inv.billable_assets == 5 and inv.total == Decimal("500.00")
    assert inv.lines[-1].line_type is InvoiceLineType.MINIMUM_COMMITMENT and inv.lines[-1].quantity == 3


def test_pending_charges_are_included() -> None:
    pending = PendingChargeInput(
        uuid.uuid4(),
        InvoiceLineType.PRORATION_CREDIT,
        Decimal("-1000.00"),
        "credit",
        date(2026, 10, 20),
        date(2026, 11, 1),
    )
    inv = compute_invoice(terms("50000"), PERIOD, assets(2), [pending], "Monthly")
    assert inv.total == Decimal("99000.00")


def test_prorate_add_daily_full_and_next_period() -> None:
    r = prorate_add(terms("30000"), PERIOD, date(2026, 11, 21), active_before=3)
    assert (r.days, r.amount) == (10, Decimal("10000.00"))
    assert prorate_add(
        terms("30000", add=MidCycleAddPolicy.FULL_PERIOD), PERIOD, date(2026, 11, 21), 3
    ).amount == Decimal("30000.00")
    assert prorate_add(terms(add=MidCycleAddPolicy.NEXT_PERIOD), PERIOD, date(2026, 11, 21), 3).amount == 0


def test_prorate_respects_minimum_commitment() -> None:
    assert prorate_add(terms(minimum=5), PERIOD, date(2026, 11, 10), active_before=4).amount == 0
    assert prorate_remove(terms(minimum=5), PERIOD, date(2026, 11, 10), active_after=4).amount == 0


def test_prorate_remove_credit_and_no_credit() -> None:
    r = prorate_remove(terms("30000"), PERIOD, date(2026, 11, 16), active_after=2)
    assert (r.days, r.amount) == (15, Decimal("-15000.00"))
    assert prorate_remove(terms(remove=MidCycleRemovePolicy.NO_CREDIT), PERIOD, date(2026, 11, 16), 2).amount == 0


def test_add_then_remove_nets_to_days_used() -> None:
    t = terms("30000")
    add = prorate_add(t, PERIOD, date(2026, 11, 5), 1)
    rem = prorate_remove(t, PERIOD, date(2026, 11, 25), 1)
    assert add.amount + rem.amount == Decimal("20000.00")
