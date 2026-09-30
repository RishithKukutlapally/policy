"""Money rounding: the domain owns quantization (NFR-01); services only call these."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

CENT: Final = Decimal("0.01")


def to_money(value: Decimal) -> Decimal:
    """``value`` quantized once to 0.01, ``ROUND_HALF_UP``."""
    return value.quantize(CENT, ROUND_HALF_UP)


def has_at_most_two_decimals(value: Decimal) -> bool:
    """True when ``value`` is finite and needs no rounding to be a money amount."""
    return value.is_finite() and value == value.quantize(CENT)
