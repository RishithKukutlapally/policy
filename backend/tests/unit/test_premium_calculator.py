"""Unit tests for `calculate_premium`: band edges, ordering, eligibility, precision."""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.domain.premium_calculator import calculate_premium
from src.types.errors import PremiumFactorNotFoundError, ValidationError
from src.types.rules import PremiumRules, RuleSet

RULES = Path(__file__).resolve().parents[2] / "policy_rules"


def _rs(folder: str) -> RuleSet:
    data: dict[str, Any] = json.loads((RULES / folder / "v1.json").read_text(encoding="utf-8"))
    return RuleSet.from_mapping(data)


def _term(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sum_insured": "5000000.00",
        "age": 35,
        "term_years": 20,
        "smoker": False,
    }
    return {**base, **over}


def _motor(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sum_insured": "2000000.00",
        "owner_age": 35,
        "vehicle_age_years": 3,
        "engine_cc": 1200,
        "zone": "A",
        "ncb_percent": "20",
    }
    return {**base, **over}


def _mult(rule_set: RuleSet, inputs: dict[str, Any], factor: str) -> Decimal:
    steps = calculate_premium(rule_set, inputs).steps
    return next(s.multiplier for s in steps if s.factor == factor)


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (18, "1.00"),
        (30, "1.00"),
        (31, "1.20"),
        (40, "1.20"),
        (41, "1.60"),
        (51, "2.20"),
        (60, "2.20"),
    ],
)
def test_term_life_age_band_edges(age: int, expected: str) -> None:
    assert _mult(_rs("term_life"), _term(age=age), "age_bands") == Decimal(expected)


@pytest.mark.parametrize(
    ("term", "expected"),
    [(5, "1.00"), (15, "1.00"), (16, "1.10"), (25, "1.10"), (26, "1.25"), (30, "1.25")],
)
def test_term_life_term_band_edges(term: int, expected: str) -> None:
    assert _mult(_rs("term_life"), _term(term_years=term), "term_years_bands") == Decimal(expected)


@pytest.mark.parametrize(
    ("veh", "expected"),
    [(0, "1.00"), (5, "1.00"), (6, "1.15"), (10, "1.15"), (11, "1.35"), (16, "1.60"), (99, "1.60")],
)
def test_motor_vehicle_age_band_edges(veh: int, expected: str) -> None:
    got = _mult(_rs("motor"), _motor(vehicle_age_years=veh), "vehicle_age_bands")
    assert got == Decimal(expected)


@pytest.mark.parametrize(
    ("cc", "expected"),
    [(1000, "1.00"), (1001, "1.10"), (1500, "1.10"), (1501, "1.25"), (99999, "1.25")],
)
def test_motor_engine_band_edges(cc: int, expected: str) -> None:
    assert _mult(_rs("motor"), _motor(engine_cc=cc), "engine_cc_bands") == Decimal(expected)


def test_motor_age_outside_bands_rejected() -> None:
    with pytest.raises(PremiumFactorNotFoundError, match="vehicle_age_bands"):
        calculate_premium(_rs("motor"), _motor(vehicle_age_years=100))


def test_factor_order_and_names() -> None:
    result = calculate_premium(_rs("motor"), _motor())
    assert result.factors_used == (
        "vehicle_age_bands",
        "engine_cc_bands",
        "zone_rates",
        "ncb_discounts",
    )
    smoker = calculate_premium(_rs("term_life"), _term(smoker=True))
    assert smoker.factors_used == ("age_bands", "term_years_bands", "smoker_loading")


@pytest.mark.parametrize(
    ("folder", "inputs"),
    [
        ("term_life", _term(age=17)),
        ("term_life", _term(age=61)),
        ("term_life", _term(sum_insured="499999.99")),
        ("motor", _motor(owner_age=76)),
        ("motor", _motor(sum_insured="5000000.01")),
    ],
)
def test_eligibility_rejection(folder: str, inputs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        calculate_premium(_rs(folder), inputs)


def test_missing_input_rejected() -> None:
    inputs = _term()
    del inputs["smoker"]
    with pytest.raises(ValidationError, match="smoker"):
        calculate_premium(_rs("term_life"), inputs)


def test_unknown_factor_key_rejected() -> None:
    rule_set = _rs("term_life")
    premium = dataclasses.replace(
        rule_set.premium, scalars={**rule_set.premium.scalars, "surprise": Decimal("0.1")}
    )
    assert isinstance(premium, PremiumRules)
    with pytest.raises(ValidationError, match="surprise"):
        calculate_premium(dataclasses.replace(rule_set, premium=premium), _term())


def test_amounts_are_two_dp_decimals_and_intermediates_unrounded() -> None:
    result = calculate_premium(_rs("motor"), _motor(sum_insured="123457.00"))
    assert isinstance(result.final_amount, Decimal)
    assert result.final_amount.as_tuple().exponent == -2
    assert result.base == Decimal("3827.16700")
    assert result.raw_amount != result.raw_amount.quantize(Decimal("0.01"))
    assert result.minimum_premium == Decimal("2500.00")
