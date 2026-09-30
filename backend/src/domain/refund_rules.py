"""Cancellation refund rules driven by the rule set's `cancellation` block (AC-08, AC-19, NFR-01).

Pure: dates are passed in; no I/O, logging or clock. The result is quantized once, at the end,
to 0.01 `ROUND_HALF_UP`.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.domain.term_days import days_elapsed, term_days
from src.types.enums import RefundType
from src.types.errors import ValidationError
from src.types.rules import RuleSet

_CENT = Decimal("0.01")
_ZERO = Decimal(0)
_ZERO_CENTS = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class RefundBreakdown:
    """Whole refund breakdown; every amount is quantized once and `amount == gross - admin_fee`."""

    refund_type: RefundType
    gross: Decimal
    admin_fee: Decimal
    amount: Decimal


def refund_breakdown(
    rule_set: RuleSet,
    premium: Decimal,
    effective_date: date,
    expiry_date: date,
    cancellation_date: date,
    *,
    new_business: bool = True,
) -> RefundBreakdown:
    """Refund type, gross pro-rata, admin fee applied and net amount for cancelling.

    Inside the free-look window (`days_elapsed <= free_look_days`) the full premium is returned
    with no fee (new business only; renewal terms get no free look); afterwards the pro-rata
    refund less the admin fee (capped at the gross), never below `0.00`. The net amount and the
    fee are each rounded once from full precision; the gross is their exact sum, so the parts
    always reconcile to the cent.
    """
    if not effective_date <= cancellation_date <= expiry_date:
        raise ValidationError(
            "cancellation_date is outside the policy term",
            [{"field": "cancellation_date", "code": "OUTSIDE_TERM"}],
        )
    rules = rule_set.cancellation
    elapsed = days_elapsed(effective_date, cancellation_date)
    if new_business and elapsed <= rules.free_look_days:
        full = premium.quantize(_CENT, ROUND_HALF_UP)
        return RefundBreakdown(RefundType.FREE_LOOK, full, _ZERO_CENTS, full)
    total = term_days(effective_date, expiry_date)
    gross_raw = premium * Decimal(total - elapsed) / Decimal(total)
    fee_raw = min(rules.admin_fee, gross_raw)
    amount = max(_ZERO, gross_raw - fee_raw).quantize(_CENT, ROUND_HALF_UP)
    fee = fee_raw.quantize(_CENT, ROUND_HALF_UP)
    return RefundBreakdown(RefundType.PRO_RATA, amount + fee, fee, amount)


def refund_amount(
    rule_set: RuleSet,
    premium: Decimal,
    effective_date: date,
    expiry_date: date,
    cancellation_date: date,
    *,
    new_business: bool = True,
) -> tuple[RefundType, Decimal]:
    """Refund type and net amount; see :func:`refund_breakdown`."""
    parts = refund_breakdown(
        rule_set, premium, effective_date, expiry_date, cancellation_date, new_business=new_business
    )
    return parts.refund_type, parts.amount
