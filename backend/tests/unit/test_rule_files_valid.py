"""Rule-file schema conformance and product distinctness (AC-02)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator, ValidationError

POLICY_RULES = Path(__file__).resolve().parents[2] / "policy_rules"
SCHEMA_PATH = POLICY_RULES / "schema" / "rule-file.schema.json"
RULE_FILES = {
    "TERM_LIFE": POLICY_RULES / "term_life" / "v1.json",
    "MOTOR": POLICY_RULES / "motor" / "v1.json",
    "HOUSEHOLD": POLICY_RULES / "household" / "v1.json",
}
EXPECTED_FACTOR_KEYS = {
    "TERM_LIFE": {"age_bands", "smoker_loading", "term_years_bands"},
    "MOTOR": {"vehicle_age_bands", "engine_cc_bands", "ncb_discounts", "zone_rates"},
    "HOUSEHOLD": {"construction_type_rates", "flood_zone_loading", "security_discount"},
}
EXPECTED_PREMIUM_HEAD = {
    "TERM_LIFE": ("0.0015", "3000.00"),
    "MOTOR": ("0.0310", "2500.00"),
    "HOUSEHOLD": ("0.0008", "1500.00"),
}
EXPECTED_ELIGIBILITY = {
    "TERM_LIFE": (18, 60, "500000.00", "50000000.00"),
    "MOTOR": (18, 75, "100000.00", "5000000.00"),
    "HOUSEHOLD": (18, 80, "500000.00", "20000000.00"),
}
PREFIX = {"TERM_LIFE": "TL", "MOTOR": "MO", "HOUSEHOLD": "HH"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator() -> Draft7Validator:
    return Draft7Validator(_load(SCHEMA_PATH))


@pytest.fixture(scope="module")
def rule_sets() -> dict[str, dict[str, Any]]:
    return {product: _load(path) for product, path in RULE_FILES.items()}


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(RULE_FILES))
def test_ac02_each_v1_file_has_the_published_header(
    product: str, rule_sets: dict[str, dict[str, Any]]
) -> None:
    data = rule_sets[product]
    assert data["product"] == product
    assert data["version"] == 1
    assert data["status"] == "PUBLISHED"
    assert data["currency"] == "INR"
    assert data["effective_from"] == "2026-01-01"


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(RULE_FILES))
def test_ac02_each_v1_file_validates_against_the_schema(
    product: str, validator: Draft7Validator, rule_sets: dict[str, dict[str, Any]]
) -> None:
    assert list(validator.iter_errors(rule_sets[product])) == []


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(RULE_FILES))
def test_ac02_product_specific_factors_and_premium_head(
    product: str, rule_sets: dict[str, dict[str, Any]]
) -> None:
    premium = rule_sets[product]["premium"]
    assert set(premium["factors"]) == EXPECTED_FACTOR_KEYS[product]
    assert (premium["base_rate"], premium["minimum_premium"]) == EXPECTED_PREMIUM_HEAD[product]


@pytest.mark.ac("AC-02")
def test_ac02_the_three_rule_sets_are_distinct(rule_sets: dict[str, dict[str, Any]]) -> None:
    premiums = [json.dumps(rs["premium"], sort_keys=True) for rs in rule_sets.values()]
    assert len(set(premiums)) == 3


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(RULE_FILES))
def test_ac02_reason_codes_use_the_product_prefix(
    product: str, rule_sets: dict[str, dict[str, Any]]
) -> None:
    codes = rule_sets[product]["underwriting"]["reason_codes"]
    assert all(code.startswith(f"{PREFIX[product]}-UW-") for code in codes)
    for manual in ("900", "901", "902"):
        assert f"{PREFIX[product]}-UW-{manual}" in codes


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(RULE_FILES))
def test_ac02_every_rule_reason_code_is_declared(
    product: str, rule_sets: dict[str, dict[str, Any]]
) -> None:
    underwriting = rule_sets[product]["underwriting"]
    for rule in underwriting["rules"]:
        assert rule["reason_code"] in underwriting["reason_codes"]


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(RULE_FILES))
def test_ac02_money_fields_are_strings(product: str, rule_sets: dict[str, dict[str, Any]]) -> None:
    data = rule_sets[product]
    money = [
        data["premium"]["base_rate"],
        data["premium"]["minimum_premium"],
        data["eligibility"]["min_sum_insured"],
        data["eligibility"]["max_sum_insured"],
        data["cancellation"]["admin_fee"],
    ]
    assert all(isinstance(value, str) for value in money)


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(RULE_FILES))
def test_ac02_eligibility_and_lifecycle_values(
    product: str, rule_sets: dict[str, dict[str, Any]]
) -> None:
    data = rule_sets[product]
    eligibility = data["eligibility"]
    assert (
        eligibility["min_age"],
        eligibility["max_age"],
        eligibility["min_sum_insured"],
        eligibility["max_sum_insured"],
    ) == EXPECTED_ELIGIBILITY[product]
    assert data["renewal"] == {"term_months": 12, "grace_period_days": 30}
    assert data["cancellation"] == {
        "method": "PRO_RATA",
        "free_look_days": 15,
        "admin_fee": "250.00",
    }


@pytest.mark.ac("AC-02")
def test_ac02_schema_rejects_a_numeric_money_value(
    validator: Draft7Validator, rule_sets: dict[str, dict[str, Any]]
) -> None:
    broken = copy.deepcopy(rule_sets["MOTOR"])
    broken["premium"]["base_rate"] = 0.031
    with pytest.raises(ValidationError) as exc:
        validator.validate(broken)
    assert list(exc.value.absolute_path)[:2] == ["premium", "base_rate"]


@pytest.mark.ac("AC-02")
def test_ac02_schema_rejects_missing_reason_codes(
    validator: Draft7Validator, rule_sets: dict[str, dict[str, Any]]
) -> None:
    broken = copy.deepcopy(rule_sets["TERM_LIFE"])
    del broken["underwriting"]["reason_codes"]
    errors = list(validator.iter_errors(broken))
    assert any(list(err.absolute_path) == ["underwriting"] for err in errors)


@pytest.mark.ac("AC-02")
def test_ac02_schema_rejects_a_malformed_reason_code(
    validator: Draft7Validator, rule_sets: dict[str, dict[str, Any]]
) -> None:
    broken = copy.deepcopy(rule_sets["HOUSEHOLD"])
    broken["underwriting"]["rules"][0]["reason_code"] = "HOUSE-1"
    errors = list(validator.iter_errors(broken))
    assert any(
        list(err.absolute_path) == ["underwriting", "rules", 0, "reason_code"] for err in errors
    )


@pytest.mark.ac("AC-02")
def test_ac02_schema_rejects_an_unknown_cancellation_method(
    validator: Draft7Validator, rule_sets: dict[str, dict[str, Any]]
) -> None:
    broken = copy.deepcopy(rule_sets["MOTOR"])
    broken["cancellation"]["method"] = "SHORT_RATE"
    errors = list(validator.iter_errors(broken))
    assert any(list(err.absolute_path) == ["cancellation", "method"] for err in errors)


@pytest.mark.ac("AC-02")
def test_ac02_schema_rejects_foreign_product_factor_keys(
    validator: Draft7Validator, rule_sets: dict[str, dict[str, Any]]
) -> None:
    broken = copy.deepcopy(rule_sets["MOTOR"])
    broken["premium"]["factors"]["age_bands"] = []
    del broken["premium"]["factors"]["zone_rates"]
    assert list(validator.iter_errors(broken)) != []
