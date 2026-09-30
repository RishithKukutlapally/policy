"""Unit tests for the rule `when` evaluator."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from src.domain.condition import evaluate_condition
from src.types.errors import ValidationError

VALUES: dict[str, Any] = {
    "sum_insured": Decimal("6000000.00"),
    "vehicle_age_years": 12,
    "in_flood_zone": True,
    "construction_type": "THATCH",
    "age_at_term_end": 75,
}


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        ("vehicle_age_years > 10", True),
        ("vehicle_age_years > 15", False),
        ("age_at_term_end > 75", False),
        ("age_at_term_end >= 75", True),
        ("age_at_term_end < 76", True),
        ("age_at_term_end <= 74", False),
        ("age_at_term_end == 75", True),
        ("age_at_term_end != 75", False),
        ("construction_type == THATCH", True),
        ("construction_type != THATCH", False),
        ("construction_type in [TIMBER, THATCH]", True),
        ("construction_type in [CONCRETE, BRICK]", False),
        ("in_flood_zone == true", True),
        ("in_flood_zone == false", False),
        ("in_flood_zone == true and sum_insured > 5000000", True),
        ("in_flood_zone == true and sum_insured > 7000000", False),
        ("sum_insured >= 6000000.00", True),
    ],
)
def test_evaluate_condition(when: str, expected: bool) -> None:
    assert evaluate_condition(when, VALUES) is expected


@pytest.mark.parametrize(
    "when",
    ["nonsense", "missing_field > 1", "construction_type > 3", "age_at_term_end in 75"],
)
def test_invalid_conditions_raise(when: str) -> None:
    with pytest.raises(ValidationError):
        evaluate_condition(when, VALUES)


def test_bool_never_equals_number() -> None:
    assert evaluate_condition("in_flood_zone == 1", VALUES) is False
