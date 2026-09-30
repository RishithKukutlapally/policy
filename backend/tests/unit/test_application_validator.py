"""Boundary values for eligibility bounds in every v1 rule file (AC-03)."""

from typing import Any

import pytest

from src.config.rule_loader import parse_rule_file, rule_file_path
from src.domain.application_validator import validate_application
from src.types.enums import ProductCode

KYC: dict[str, Any] = {
    "full_name": "Test Customer 01",
    "date_of_birth": "1996-04-01",
    "aadhaar": "999900000001",
    "pan": "AAAAA0001A",
    "address": "1 Sample Street, Testville",
}
BASE: dict[ProductCode, dict[str, Any]] = {
    ProductCode.MOTOR: {
        "owner_age": 30,
        "vehicle_age_years": 3,
        "engine_cc": 1200,
        "zone": "B",
        "ncb_percent": "0",
    },
    ProductCode.TERM_LIFE: {"age": 30, "term_years": 10, "smoker": False},
    ProductCode.HOUSEHOLD: {
        "proposer_age": 30,
        "construction_type": "BRICK",
        "in_flood_zone": False,
        "has_security_system": False,
    },
}
HEALTH = {"has_pre_existing_condition": False}
AGE_FIELD = {
    ProductCode.MOTOR: "owner_age",
    ProductCode.TERM_LIFE: "age",
    ProductCode.HOUSEHOLD: "proposer_age",
}
LIMITS = {
    ProductCode.MOTOR: (18, 75, "100000.00", "5000000.00"),
    ProductCode.TERM_LIFE: (18, 60, "500000.00", "50000000.00"),
    ProductCode.HOUSEHOLD: (18, 80, "500000.00", "20000000.00"),
}


def run(product: ProductCode, **patch: Any) -> list[tuple[str, str]]:
    risk = {**BASE[product], "sum_insured": LIMITS[product][2], **patch}
    rule_set = parse_rule_file(rule_file_path(product, 1))
    return [tuple(e) for e in validate_application(rule_set, KYC, risk, HEALTH)]  # type: ignore[misc]


@pytest.mark.parametrize("product", list(ProductCode))
def test_age_boundaries(product: ProductCode) -> None:
    low, high, _, _ = LIMITS[product]
    field = AGE_FIELD[product]
    assert run(product, **{field: low}) == []
    assert run(product, **{field: high}) == []
    assert run(product, **{field: low - 1}) == [(field, "OUT_OF_RANGE")]
    assert run(product, **{field: high + 1}) == [(field, "OUT_OF_RANGE")]


@pytest.mark.parametrize("product", list(ProductCode))
def test_sum_insured_boundaries(product: ProductCode) -> None:
    _, _, low, high = LIMITS[product]
    assert run(product, sum_insured=low) == []
    assert run(product, sum_insured=high) == []
    assert run(product, sum_insured="0.00") == [("sum_insured", "OUT_OF_RANGE")]
    assert run(product, sum_insured=str(float(high) + 0.01)) == [("sum_insured", "OUT_OF_RANGE")]
    assert run(product, sum_insured="abc") == [("sum_insured", "INVALID_FORMAT")]
    assert run(product, sum_insured=1.5) == [("sum_insured", "INVALID_FORMAT")]


def test_type_and_enum_findings() -> None:
    assert run(ProductCode.MOTOR, owner_age="30") == [("owner_age", "INVALID_FORMAT")]
    assert run(ProductCode.MOTOR, vehicle_age_years=-1) == [("vehicle_age_years", "OUT_OF_RANGE")]
    assert run(ProductCode.MOTOR, ncb_percent="99") == [("ncb_percent", "INVALID_FORMAT")]
    assert run(ProductCode.TERM_LIFE, smoker="no") == [("smoker", "INVALID_FORMAT")]
    assert run(ProductCode.HOUSEHOLD, construction_type="STRAW") == [
        ("construction_type", "INVALID_FORMAT")
    ]
    assert run(ProductCode.HOUSEHOLD, in_flood_zone=None) == [("in_flood_zone", "REQUIRED")]


def test_bad_health_declaration_and_no_date() -> None:
    rule_set = parse_rule_file(rule_file_path(ProductCode.TERM_LIFE, 1))
    risk = {**BASE[ProductCode.TERM_LIFE], "sum_insured": "500000"}
    found = validate_application(rule_set, KYC, risk, {"details": "x"})
    assert found == [("health_declaration.has_pre_existing_condition", "REQUIRED")]
