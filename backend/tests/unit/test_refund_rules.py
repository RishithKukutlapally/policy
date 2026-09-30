"""Unit tests for pure refund rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from src.domain.refund_rules import refund_amount, refund_breakdown
from src.types.enums import RefundType
from src.types.rules import RuleSet

_RULES = Path(__file__).resolve().parents[2] / "policy_rules"
_RS = RuleSet.from_mapping(json.loads((_RULES / "term_life" / "v1.json").read_text("utf-8")))
_EFF, _EXP = date(2026, 1, 1), date(2026, 12, 31)


def test_free_look_boundary_is_inclusive() -> None:
    assert refund_amount(_RS, Decimal("100.00"), _EFF, _EXP, date(2026, 1, 16))[0] is (
        RefundType.FREE_LOOK
    )
    assert refund_amount(_RS, Decimal("12000.00"), _EFF, _EXP, date(2026, 1, 17))[0] is (
        RefundType.PRO_RATA
    )


def test_leap_year_term_uses_366_days() -> None:
    kind, amount = refund_amount(
        _RS, Decimal("36600.00"), date(2028, 1, 1), date(2028, 12, 31), date(2028, 7, 1)
    )
    # elapsed 182, unused 184 of 366 -> 18400.00 - 250.00
    assert (kind, amount) == (RefundType.PRO_RATA, Decimal("18150.00"))


def test_last_day_has_one_unused_day_and_floors_to_zero() -> None:
    _, amount = refund_amount(_RS, Decimal("12000.00"), _EFF, _EXP, _EXP)
    assert amount == Decimal("0.00")
    assert str(amount) == "0.00"


def test_refund_is_quantized_once_at_the_end() -> None:
    premium = Decimal("1000000.01")
    _, amount = refund_amount(_RS, premium, _EFF, _EXP, date(2026, 3, 1))
    exact = premium * 306 / 365 - Decimal("250.00")
    assert amount == exact.quantize(Decimal("0.01"), ROUND_HALF_UP)
    assert amount.as_tuple().exponent == -2


def test_free_look_amount_keeps_two_dp() -> None:
    _, amount = refund_amount(_RS, Decimal("12000"), _EFF, _EXP, date(2026, 1, 2))
    assert str(amount) == "12000.00"


def _rule_set_with_fee(fee: str) -> RuleSet:
    raw = json.loads((_RULES / "term_life" / "v1.json").read_text("utf-8"))
    raw["cancellation"]["admin_fee"] = fee
    return RuleSet.from_mapping(raw)


def _assert_two_dp(*values: Decimal) -> None:
    for value in values:
        assert isinstance(value, Decimal)
        assert value.as_tuple().exponent == -2


_CENT = Decimal("0.01")
_CANCEL = date(2026, 6, 1)


def _expected_gross(premium: Decimal) -> Decimal:
    """Independent pro-rata gross for ``_CANCEL``, derived from the fixture dates."""
    term = (_EXP - _EFF).days + 1
    unused = (_EXP - _CANCEL).days + 1
    return (premium * Decimal(unused) / Decimal(term)).quantize(_CENT, ROUND_HALF_UP)


def test_breakdown_is_internally_consistent_pro_rata() -> None:
    premium = Decimal("12000.00")
    parts = refund_breakdown(_RS, premium, _EFF, _EXP, _CANCEL)
    assert parts.refund_type is RefundType.PRO_RATA
    _assert_two_dp(parts.gross, parts.admin_fee, parts.amount)
    assert parts.amount == parts.gross - parts.admin_fee
    gross, fee = _expected_gross(premium), Decimal("250.00")
    assert (parts.gross, parts.admin_fee, parts.amount) == (gross, fee, gross - fee)


def test_breakdown_free_look_has_no_fee() -> None:
    parts = refund_breakdown(_RS, Decimal("15500"), _EFF, _EXP, date(2026, 1, 2))
    assert parts.refund_type is RefundType.FREE_LOOK
    assert (parts.gross, parts.admin_fee, parts.amount) == (
        Decimal("15500.00"),
        Decimal("0.00"),
        Decimal("15500.00"),
    )
    _assert_two_dp(parts.gross, parts.admin_fee, parts.amount)


def test_breakdown_non_exact_cent_fee_is_rounded_once() -> None:
    """Fee 250.005: one rounding of the exact net; gross - fee agrees with net to the cent."""
    rule_set = _rule_set_with_fee("250.005")
    premium = Decimal("12000.00")
    parts = refund_breakdown(rule_set, premium, _EFF, _EXP, _CANCEL)
    term = (_EXP - _EFF).days + 1
    unused = (_EXP - _CANCEL).days + 1
    exact_net = premium * Decimal(unused) / Decimal(term) - Decimal("250.005")
    rounded_once = exact_net.quantize(_CENT, ROUND_HALF_UP)
    assert parts.amount == rounded_once
    assert parts.admin_fee == Decimal("250.01")
    assert parts.amount == parts.gross - parts.admin_fee
    _assert_two_dp(parts.gross, parts.admin_fee, parts.amount)
    assert refund_amount(rule_set, premium, _EFF, _EXP, _CANCEL)[1] == parts.amount


def test_breakdown_fee_capped_at_gross_and_amount_floors_at_zero() -> None:
    parts = refund_breakdown(_RS, Decimal("12000.00"), _EFF, _EXP, _EXP)
    assert parts.amount == Decimal("0.00")
    assert parts.admin_fee == parts.gross
    _assert_two_dp(parts.gross, parts.admin_fee, parts.amount)
