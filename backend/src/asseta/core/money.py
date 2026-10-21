"""Fixed-point money helpers. Floats are rejected; rounding is explicit and configurable by caller."""

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from enum import StrEnum


class RoundingMode(StrEnum):
    HALF_UP = "HALF_UP"
    HALF_EVEN = "HALF_EVEN"


_ROUNDING = {RoundingMode.HALF_UP: ROUND_HALF_UP, RoundingMode.HALF_EVEN: ROUND_HALF_EVEN}


def to_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, float):  # defensive: callers must never pass floats
        raise TypeError("float is not allowed for money")
    return value if isinstance(value, Decimal) else Decimal(value)


def quantize(amount: Decimal, minor_units: int, mode: RoundingMode = RoundingMode.HALF_UP) -> Decimal:
    exponent = Decimal(1).scaleb(-minor_units)
    return amount.quantize(exponent, rounding=_ROUNDING[mode])
