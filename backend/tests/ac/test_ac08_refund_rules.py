"""AC-08 / AC-19: refund figures from the real v1 rule files (NFR-01)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.domain.refund_rules import refund_amount
from src.types.enums import RefundType
from src.types.errors import ValidationError
from src.types.rules import RuleSet

RULES = Path(__file__).resolve().parents[2] / "policy_rules"


def _rs(folder: str) -> RuleSet:
    data: dict[str, Any] = json.loads((RULES / folder / "v1.json").read_text(encoding="utf-8"))
    return RuleSet.from_mapping(data)


PRO_RATA_CASES = [
    ("motor", "12400.00", date(2026, 10, 1), date(2027, 9, 30), date(2027, 4, 1), "5966.99"),
    ("motor", "12400.00", date(2026, 10, 1), date(2027, 9, 30), date(2027, 9, 25), "0.00"),
    ("motor", "12400.00", date(2026, 10, 1), date(2027, 9, 30), date(2026, 10, 17), "11606.44"),
    ("motor", "14720.00", date(2027, 1, 1), date(2027, 12, 31), date(2027, 1, 5), "14308.68"),
    ("term_life", "12000.00", date(2026, 1, 1), date(2026, 12, 31), date(2026, 4, 1), "8791.10"),
    ("term_life", "12000.00", date(2026, 1, 1), date(2026, 12, 31), date(2026, 1, 17), "11223.97"),
    ("term_life", "2500.00", date(2026, 1, 1), date(2026, 12, 31), date(2026, 12, 1), "0.00"),
]


@pytest.mark.ac("AC-08")
@pytest.mark.ac("AC-19")
@pytest.mark.parametrize(("product", "premium", "eff", "exp", "on", "expected"), PRO_RATA_CASES)
def test_ac08_pro_rata_refund_figures(
    product: str, premium: str, eff: date, exp: date, on: date, expected: str
) -> None:
    kind, amount = refund_amount(
        _rs(product),
        Decimal(premium),
        eff,
        exp,
        on,
        new_business=product != "motor" or premium == "12400.00",
    )
    assert kind is RefundType.PRO_RATA
    assert amount == Decimal(expected)
    assert amount.as_tuple().exponent == -2


@pytest.mark.ac("AC-19")
@pytest.mark.parametrize("on", [date(2026, 1, 1), date(2026, 1, 10), date(2026, 1, 16)])
def test_ac19_free_look_refunds_full_premium(on: date) -> None:
    kind, amount = refund_amount(
        _rs("term_life"), Decimal("12000.00"), date(2026, 1, 1), date(2026, 12, 31), on
    )
    assert (kind, amount) == (RefundType.FREE_LOOK, Decimal("12000.00"))


@pytest.mark.ac("AC-08")
@pytest.mark.parametrize("on", [date(2025, 12, 31), date(2027, 1, 1)])
def test_ac08_date_outside_term_rejected(on: date) -> None:
    with pytest.raises(ValidationError) as exc:
        refund_amount(
            _rs("term_life"), Decimal("12000.00"), date(2026, 1, 1), date(2026, 12, 31), on
        )
    assert exc.value.details == [{"field": "cancellation_date", "code": "OUTSIDE_TERM"}]
