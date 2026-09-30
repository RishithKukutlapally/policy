"""AC-16: endorsement types are validated against the rule set; a sum-insured change re-rates."""

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from src.config.rule_loader import load_rule_file
from src.domain.endorsement_rules import premium_delta, validate_endorsement
from src.types.enums import EndorsementType, ProductCode
from src.types.rules import EndorsementRules, RuleSet

_MOTOR = load_rule_file(ProductCode.MOTOR, 1)
_LIFE = load_rule_file(ProductCode.TERM_LIFE, 1)


def _motor(sum_insured: str) -> dict[str, Any]:
    return {
        "sum_insured": Decimal(sum_insured),
        "owner_age": 30,
        "vehicle_age_years": 2,
        "engine_cc": 998,
        "zone": "B",
        "ncb_percent": "0",
    }


def _life(sum_insured: str) -> dict[str, Any]:
    return {"sum_insured": Decimal(sum_insured), "age": 25, "term_years": 10, "smoker": False}


def _only(rule_set: RuleSet, *allowed: EndorsementType) -> RuleSet:
    return replace(rule_set, endorsement=EndorsementRules(allowed_types=frozenset(allowed)))


@pytest.mark.ac("AC-16")
def test_ac16_motor_increase_delta_is_prorated_and_rounded_once() -> None:
    """AC-16: MOTOR 400000 -> 500000 over 183/365 unused days gives 1554.25."""
    delta = premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), 183, 365)
    assert delta == Decimal("1554.25")


@pytest.mark.ac("AC-16")
def test_ac16_motor_decrease_delta_is_negative_same_magnitude() -> None:
    """AC-16: the reverse change yields -1554.25."""
    delta = premium_delta(_MOTOR, _motor("500000.00"), _motor("400000.00"), 183, 365)
    assert delta == Decimal("-1554.25")


@pytest.mark.ac("AC-16")
def test_ac16_term_life_delta_1495_89() -> None:
    """AC-16: TERM_LIFE 12000.00 -> 15000.00 over 182/365 gives 1495.89 (and its negation)."""
    up = premium_delta(_LIFE, _life("8000000.00"), _life("10000000.00"), 182, 365)
    down = premium_delta(_LIFE, _life("10000000.00"), _life("8000000.00"), 182, 365)
    assert (up, down) == (Decimal("1495.89"), Decimal("-1495.89"))


@pytest.mark.ac("AC-16")
def test_ac16_motor_delta_1537_26() -> None:
    """AC-16: MOTOR 15500.00 -> 18600.00 over 181/365 gives 1537.26."""
    delta = premium_delta(_MOTOR, _motor("500000.00"), _motor("600000.00"), 181, 365)
    assert delta == Decimal("1537.26")


@pytest.mark.ac("AC-16")
@pytest.mark.parametrize("kind", [EndorsementType.CHANGE_ADDRESS, EndorsementType.ADD_NOMINEE])
def test_ac16_non_priced_types_have_zero_delta(kind: EndorsementType) -> None:
    """AC-16: CHANGE_ADDRESS and ADD_NOMINEE never change the premium."""
    delta = premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), 183, 365, kind)
    assert delta == Decimal("0.00")
    assert delta.as_tuple().exponent == -2


@pytest.mark.ac("AC-16")
def test_ac16_type_not_in_allowed_types_is_not_allowed() -> None:
    """AC-16: a type absent from endorsement.allowed_types is rejected as NOT_ALLOWED."""
    rule_set = _only(_MOTOR, EndorsementType.CHANGE_ADDRESS)
    findings = validate_endorsement(
        rule_set, EndorsementType.ADD_NOMINEE, {}, {"nominee_name": "A", "relationship": "SPOUSE"}
    )
    assert ("endorsement_type", "NOT_ALLOWED") in findings


@pytest.mark.ac("AC-16")
def test_ac16_all_listed_types_validate_on_full_rule_set() -> None:
    """AC-16: each of the three types is accepted with a valid payload on the v1 rule set."""
    current = {"sum_insured": Decimal("400000.00")}
    good = {
        EndorsementType.CHANGE_ADDRESS: {"address": "1 Sample Street"},
        EndorsementType.ADD_NOMINEE: {"nominee_name": "A", "relationship": "SPOUSE"},
        EndorsementType.CHANGE_SUM_INSURED: {"new_sum_insured": Decimal("500000.00")},
    }
    for kind, payload in good.items():
        assert validate_endorsement(_MOTOR, kind, current, payload) == []


@pytest.mark.ac("AC-16")
@pytest.mark.parametrize(
    ("value", "ok"),
    [("99999.99", False), ("5000000.01", False), ("100000.00", True), ("5000000.00", True)],
)
def test_ac16_sum_insured_bounds(value: str, ok: bool) -> None:
    """AC-16: new sum insured must lie within eligibility min/max inclusive."""
    findings = validate_endorsement(
        _MOTOR,
        EndorsementType.CHANGE_SUM_INSURED,
        {"sum_insured": Decimal("400000.00")},
        {"new_sum_insured": Decimal(value)},
    )
    assert (("new_sum_insured", "OUT_OF_RANGE") not in findings) is ok


@pytest.mark.ac("AC-16")
def test_ac16_unchanged_and_missing_fields_are_reported() -> None:
    """AC-16: unchanged sum insured is UNCHANGED; missing payload fields are REQUIRED."""
    kind = EndorsementType.CHANGE_SUM_INSURED
    same = validate_endorsement(
        _MOTOR, kind, {"sum_insured": Decimal("400000.00")}, {"new_sum_insured": "400000.00"}
    )
    assert same == [("new_sum_insured", "UNCHANGED")]
    blank = validate_endorsement(_MOTOR, EndorsementType.CHANGE_ADDRESS, {}, {"address": " "})
    assert blank == [("address", "REQUIRED")]
    missing = validate_endorsement(_MOTOR, EndorsementType.ADD_NOMINEE, {}, {})
    assert ("nominee_name", "REQUIRED") in missing
    assert ("relationship", "REQUIRED") in missing


@pytest.mark.ac("AC-16")
def test_ac16_nominee_shares_over_100_rejected() -> None:
    """AC-16: existing plus new nominee shares above 100 give SHARE_EXCEEDS_100."""
    findings = validate_endorsement(
        _MOTOR,
        EndorsementType.ADD_NOMINEE,
        {"nominee_share_total": Decimal("70")},
        {"nominee_name": "A", "relationship": "SPOUSE", "share_percent": Decimal("40")},
    )
    assert ("share_percent", "SHARE_EXCEEDS_100") in findings
