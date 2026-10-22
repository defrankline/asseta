"""Per-line settlement: payables absorb negative lines proportionally and always sum to the total; explicit line
allocations apply first, invoice-level money fills the rest in line order."""

import uuid
from decimal import Decimal

from asseta.modules.platform_billing.settlement import LineInput, payables, settle

D = Decimal


def lines(*amounts: str) -> list[LineInput]:
    return [LineInput(uuid.uuid4(), i + 1, D(a)) for i, a in enumerate(amounts)]


def test_payables_spread_discount_and_sum_to_total() -> None:
    ls = lines("100000", "100000", "-20000", "28800")  # 2 assets, 10% discount, VAT
    due = payables(ls)
    assert sum(due.values()) == D("208800")
    assert [due[x.line_id] for x in ls] == [D("91258.7413"), D("91258.7413"), D(0), D("26282.5174")]


def test_explicit_first_then_waterfall_in_line_order() -> None:
    ls = lines("100", "50", "30")
    states = settle(ls, [(ls[2].line_id, D("30")), (None, D("120"))])
    assert [(s.paid, s.settled) for s in states] == [(D("100"), True), (D("20"), False), (D("30"), True)]


def test_nothing_payable_on_zero_or_credit_invoices() -> None:
    ls = lines("10", "-10")
    assert all(not s.settled for s in settle(ls, [(None, D("5"))]))
