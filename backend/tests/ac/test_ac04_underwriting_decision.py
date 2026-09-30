"""AC-04: underwriting decisions and reason codes come from the active rule version."""

from dataclasses import replace
from typing import Any

import pytest

from src.config.rule_loader import parse_rule_file, rule_file_path
from src.domain.underwriting_rules import UnknownReasonCodeError, decide
from src.types.enums import Decision, ProductCode
from src.types.rules import RuleSet, UnderwritingRule, UnderwritingRules


def load(product: ProductCode) -> RuleSet:
    return parse_rule_file(rule_file_path(product, 1))


MOTOR_OK = {"sum_insured": "500000.00", "vehicle_age_years": 3}
CASES: list[Any] = [
    (ProductCode.MOTOR, MOTOR_OK, Decision.AUTO_BIND, ()),
    (
        ProductCode.MOTOR,
        {**MOTOR_OK, "vehicle_age_years": 12},
        Decision.MANUAL_REVIEW,
        ("MO-UW-002",),
    ),
    (
        ProductCode.MOTOR,
        {"sum_insured": "3000000.00", "vehicle_age_years": 16},
        Decision.DECLINE,
        ("MO-UW-001", "MO-UW-002", "MO-UW-003"),
    ),
    (
        ProductCode.TERM_LIFE,
        {"sum_insured": "1000000.00", "age": 50, "term_years": 30},
        Decision.DECLINE,
        ("TL-UW-001",),
    ),
    (
        ProductCode.TERM_LIFE,
        {
            "sum_insured": "1000000.00",
            "age": 35,
            "term_years": 20,
            "has_pre_existing_condition": True,
        },
        Decision.MANUAL_REVIEW,
        ("TL-UW-003",),
    ),
    (
        ProductCode.TERM_LIFE,
        {"sum_insured": "1000000.00", "age": 35, "term_years": 20},
        Decision.AUTO_BIND,
        (),
    ),
    (
        ProductCode.HOUSEHOLD,
        {"sum_insured": "1000000.00", "construction_type": "THATCH", "in_flood_zone": False},
        Decision.DECLINE,
        ("HH-UW-001",),
    ),
    (
        ProductCode.HOUSEHOLD,
        {"sum_insured": "6000000.00", "construction_type": "BRICK", "in_flood_zone": True},
        Decision.MANUAL_REVIEW,
        ("HH-UW-002",),
    ),
    (
        ProductCode.HOUSEHOLD,
        {"sum_insured": "1000000.00", "construction_type": "BRICK", "in_flood_zone": False},
        Decision.AUTO_BIND,
        (),
    ),
]


@pytest.mark.ac("AC-04")
@pytest.mark.parametrize(("product", "inputs", "decision", "codes"), CASES)
def test_ac04_outcome_and_reason_codes_from_v1(
    product: ProductCode, inputs: dict[str, Any], decision: Decision, codes: tuple[str, ...]
) -> None:
    """AC-04: each product yields all three outcomes with the v1 reason codes."""
    rule_set = load(product)
    outcome = decide(rule_set, inputs)
    assert outcome.decision is decision
    assert outcome.reason_codes == codes
    assert outcome.rule_version == 1
    assert set(outcome.reason_codes) <= set(rule_set.underwriting.reason_codes)


@pytest.mark.ac("AC-04")
def test_ac04_reason_codes_come_from_active_version_not_hardcoded() -> None:
    """AC-04: a rule set with different codes yields those codes and its version."""
    base = load(ProductCode.MOTOR)
    rules = UnderwritingRules(
        rules=(UnderwritingRule("vehicle_age_years > 10", Decision.DECLINE, "MO-UW-777"),),
        reason_codes={"MO-UW-777": "custom"},
    )
    outcome = decide(
        replace(base, version=2, underwriting=rules), MOTOR_OK | {"vehicle_age_years": 11}
    )
    assert (outcome.decision, outcome.reason_codes, outcome.rule_version) == (
        Decision.DECLINE,
        ("MO-UW-777",),
        2,
    )


@pytest.mark.ac("AC-04")
def test_ac04_unknown_reason_code_raises() -> None:
    """AC-04: a rule referencing an undefined reason code raises."""
    base = load(ProductCode.MOTOR)
    rules = UnderwritingRules(
        rules=(UnderwritingRule("vehicle_age_years > 15", Decision.DECLINE, "MO-UW-999"),),
        reason_codes=base.underwriting.reason_codes,
    )
    with pytest.raises(UnknownReasonCodeError):
        decide(replace(base, underwriting=rules), MOTOR_OK)
