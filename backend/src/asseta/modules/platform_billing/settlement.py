"""Pure per-line settlement of a platform invoice (no I/O).

* Each positive line's *payable* is its amount less its proportional share of the invoice's negative lines
  (discount, proration credits), so payables always sum to the invoice total; the last positive line takes the
  rounding remainder. Zero/negative lines have nothing to pay.
* Line-specific allocations (explicit, by the platform owner) apply to their line first; invoice-level allocations
  (`line_id` None — the default) then fill the remaining lines in line order.
"""

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

SCALE = Decimal("0.0001")  # storage scale of MONEY
ZERO = Decimal(0)


@dataclass(frozen=True)
class LineInput:
    line_id: uuid.UUID
    line_no: int
    amount: Decimal


@dataclass(frozen=True)
class LineState:
    line_id: uuid.UUID
    line_no: int
    payable: Decimal
    paid: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.payable - self.paid

    @property
    def settled(self) -> bool:
        return self.payable > 0 and self.paid >= self.payable


def payables(lines: list[LineInput]) -> dict[uuid.UUID, Decimal]:
    ordered = sorted(lines, key=lambda x: x.line_no)
    positive = [x for x in ordered if x.amount > 0]
    gross = sum((x.amount for x in positive), ZERO)
    negative = sum((x.amount for x in ordered if x.amount < 0), ZERO)
    out = {x.line_id: ZERO for x in ordered}
    if gross <= 0 or gross + negative <= 0:
        return out
    left = gross + negative
    for i, x in enumerate(positive):
        if i == len(positive) - 1:
            out[x.line_id] = left
        else:
            share = (x.amount + negative * x.amount / gross).quantize(SCALE, rounding=ROUND_HALF_EVEN)
            out[x.line_id] = share
            left -= share
    return out


def settle(lines: list[LineInput], allocations: list[tuple[uuid.UUID | None, Decimal]]) -> list[LineState]:
    """`allocations`: active (line_id or None, amount) pairs from verified payments and credits."""
    due = payables(lines)
    explicit: dict[uuid.UUID, Decimal] = {}
    pool = ZERO
    for line_id, amount in allocations:
        if line_id is None:
            pool += amount
        else:
            explicit[line_id] = explicit.get(line_id, ZERO) + amount
    states = []
    for x in sorted(lines, key=lambda line: line.line_no):
        paid = min(explicit.get(x.line_id, ZERO), due[x.line_id])
        take = min(pool, max(due[x.line_id] - paid, ZERO))
        pool -= take
        states.append(LineState(x.line_id, x.line_no, due[x.line_id], paid + take))
    return states
