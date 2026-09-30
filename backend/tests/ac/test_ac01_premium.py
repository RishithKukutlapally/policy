"""AC-01 / AC-02: golden premiums from the real v1 rule files (NFR-01)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.domain.premium_calculator import calculate_premium
from src.types.errors import PremiumFactorNotFoundError
from src.types.rules import RuleSet

RULES = Path(__file__).resolve().parents[2] / "policy_rules"


def _rs(folder: str) -> RuleSet:
    data: dict[str, Any] = json.loads((RULES / folder / "v1.json").read_text(encoding="utf-8"))
    return RuleSet.from_mapping(data)


def _motor(si: str, veh: int, cc: int, zone: str, ncb: str) -> dict[str, Any]:
    return {
        "sum_insured": si,
        "owner_age": 35,
        "vehicle_age_years": veh,
        "engine_cc": cc,
        "zone": zone,
        "ncb_percent": ncb,
    }


def _term(smoker: bool) -> dict[str, Any]:
    return {"sum_insured": "5000000.00", "age": 35, "term_years": 20, "smoker": smoker}


def _house(si: str, flood: bool, security: bool) -> dict[str, Any]:
    return {
        "sum_insured": si,
        "proposer_age": 40,
        "construction_type": "BRICK",
        "in_flood_zone": flood,
        "has_security_system": security,
    }


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    ("folder", "inputs", "expected"),
    [
        ("motor", _motor("500000.00", 3, 1200, "A", "20"), "14322.00"),
        ("motor", _motor("100000.00", 2, 900, "B", "50"), "2500.00"),
        ("motor", _motor("123457.00", 3, 1200, "A", "20"), "3536.30"),
        ("term_life", _term(False), "9900.00"),
        ("term_life", _term(True), "14850.00"),
        ("household", _house("3000000.00", True, True), "2700.00"),
        ("household", _house("3000625.00", True, False), "3000.63"),
    ],
)
def test_ac01_golden_premiums(folder: str, inputs: dict[str, Any], expected: str) -> None:
    """AC-01: golden inputs give the exact Decimal premium, quantized half-up once."""
    result = calculate_premium(_rs(folder), inputs).final_amount
    assert result == Decimal(expected)
    assert result.as_tuple().exponent == -2


@pytest.mark.ac("AC-01")
def test_ac01_minimum_premium_floor_applied() -> None:
    """AC-01: raw 1550.00 is floored to the 2500.00 minimum premium."""
    breakdown = calculate_premium(_rs("motor"), _motor("100000.00", 2, 900, "B", "50"))
    assert breakdown.raw_amount == Decimal("1550.0000")
    assert breakdown.final_amount == Decimal("2500.00")


@pytest.mark.ac("AC-01")
def test_ac01_determinism_repeated_calls() -> None:
    """AC-01: 1000 repeated calls yield a single identical result."""
    rule_set = _rs("motor")
    inputs = _motor("123457.00", 3, 1200, "A", "20")
    results = {calculate_premium(rule_set, inputs) for _ in range(1000)}
    assert len(results) == 1


@pytest.mark.ac("AC-01")
def test_ac01_records_product_and_version() -> None:
    """AC-01: the breakdown records product and rule version."""
    breakdown = calculate_premium(_rs("household"), _house("3000000.00", True, True))
    assert (breakdown.product.value, breakdown.rule_version) == ("HOUSEHOLD", 1)


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    ("inputs", "factor"),
    [
        (_motor("500000.00", 3, 100000, "A", "20"), "engine_cc_bands"),
        (_motor("500000.00", 3, 1200, "Z", "20"), "zone_rates"),
        (_motor("500000.00", 3, 1200, "A", "30"), "ncb_discounts"),
    ],
)
def test_ac01_unknown_factor_raises_naming_factor(inputs: dict[str, Any], factor: str) -> None:
    """AC-01: inputs outside every band raise, naming the factor."""
    with pytest.raises(PremiumFactorNotFoundError, match=factor):
        calculate_premium(_rs("motor"), inputs)


@pytest.mark.ac("AC-02")
def test_ac02_three_products_give_distinct_premiums() -> None:
    """AC-02: comparable inputs on the three products yield three different premiums."""
    term = calculate_premium(_rs("term_life"), _term(False)).final_amount
    motor = calculate_premium(_rs("motor"), _motor("5000000.00", 3, 1200, "A", "20")).final_amount
    house = calculate_premium(_rs("household"), _house("5000000.00", True, False)).final_amount
    assert len({term, motor, house}) == 3
