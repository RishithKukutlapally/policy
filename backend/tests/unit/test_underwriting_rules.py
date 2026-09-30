"""Boundary values at every v1 underwriting threshold (AC-04)."""

from typing import Any

import pytest

from src.config.rule_loader import parse_rule_file, rule_file_path
from src.domain.underwriting_rules import decide
from src.types.enums import Decision, ProductCode

M, T, H = ProductCode.MOTOR, ProductCode.TERM_LIFE, ProductCode.HOUSEHOLD
AB, MR, DE = Decision.AUTO_BIND, Decision.MANUAL_REVIEW, Decision.DECLINE

BOUNDARIES: list[Any] = [
    (M, {"sum_insured": "100000", "vehicle_age_years": 10}, AB, ()),
    (M, {"sum_insured": "100000", "vehicle_age_years": 11}, MR, ("MO-UW-002",)),
    (M, {"sum_insured": "100000", "vehicle_age_years": 15}, MR, ("MO-UW-002",)),
    (M, {"sum_insured": "100000", "vehicle_age_years": 16}, DE, ("MO-UW-001", "MO-UW-002")),
    (M, {"sum_insured": "2500000", "vehicle_age_years": 1}, AB, ()),
    (M, {"sum_insured": "2500000.01", "vehicle_age_years": 1}, MR, ("MO-UW-003",)),
    (T, {"sum_insured": "1000000", "age": 45, "term_years": 30}, AB, ()),
    (T, {"sum_insured": "1000000", "age": 46, "term_years": 30}, DE, ("TL-UW-001",)),
    (T, {"sum_insured": "10000000", "age": 30, "term_years": 10}, AB, ()),
    (T, {"sum_insured": "10000000.01", "age": 30, "term_years": 10}, MR, ("TL-UW-002",)),
    (
        T,
        {
            "sum_insured": "10000001",
            "age": 30,
            "term_years": 10,
            "has_pre_existing_condition": True,
        },
        MR,
        ("TL-UW-002", "TL-UW-003"),
    ),
    (
        T,
        {
            "sum_insured": "1000000",
            "age": 30,
            "term_years": 10,
            "has_pre_existing_condition": False,
        },
        AB,
        (),
    ),
    (H, {"sum_insured": "5000000", "construction_type": "BRICK", "in_flood_zone": True}, AB, ()),
    (
        H,
        {"sum_insured": "5000001", "construction_type": "BRICK", "in_flood_zone": True},
        MR,
        ("HH-UW-002",),
    ),
    (H, {"sum_insured": "9000000", "construction_type": "BRICK", "in_flood_zone": False}, AB, ()),
    (H, {"sum_insured": "9000000", "construction_type": "TIMBER", "in_flood_zone": False}, AB, ()),
    (
        H,
        {"sum_insured": "6000000", "construction_type": "THATCH", "in_flood_zone": True},
        DE,
        ("HH-UW-001", "HH-UW-002"),
    ),
]


@pytest.mark.parametrize(("product", "inputs", "decision", "codes"), BOUNDARIES)
def test_underwriting_threshold_boundaries(
    product: ProductCode, inputs: dict[str, Any], decision: Decision, codes: tuple[str, ...]
) -> None:
    outcome = decide(parse_rule_file(rule_file_path(product, 1)), inputs)
    assert (outcome.decision, outcome.reason_codes) == (decision, codes)
