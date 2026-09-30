"""Rule-set value objects are frozen and money is Decimal, never float (NFR-01, NFR-02)."""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.types.enums import Decision, EndorsementType, ProductCode, RefundType, RuleSetStatus
from src.types.errors import InvalidPolicyStateException, PolicyForgeError
from src.types.rules import RuleSet

POLICY_RULES = Path(__file__).resolve().parents[2] / "policy_rules"


def _rule_set(product_folder: str) -> RuleSet:
    data: dict[str, Any] = json.loads(
        (POLICY_RULES / product_folder / "v1.json").read_text(encoding="utf-8")
    )
    return RuleSet.from_mapping(data)


@pytest.fixture
def motor() -> RuleSet:
    return _rule_set("motor")


def test_rule_set_header_is_typed(motor: RuleSet) -> None:
    assert motor.product is ProductCode.MOTOR
    assert motor.status is RuleSetStatus.PUBLISHED
    assert motor.effective_from.isoformat() == "2026-01-01"
    assert motor.version == 1


def test_money_and_rates_are_decimal(motor: RuleSet) -> None:
    assert type(motor.premium.base_rate) is Decimal
    assert motor.premium.base_rate == Decimal("0.0310")
    assert motor.premium.minimum_premium == Decimal("2500.00")
    assert motor.cancellation.admin_fee == Decimal("250.00")
    assert motor.eligibility.max_sum_insured == Decimal("5000000.00")


def test_no_float_anywhere_in_a_loaded_rule_set(motor: RuleSet) -> None:
    values = [
        motor.premium.base_rate,
        motor.premium.minimum_premium,
        motor.eligibility.min_sum_insured,
        motor.cancellation.admin_fee,
        *(band.multiplier for table in motor.premium.bands.values() for band in table),
        *(rate for table in motor.premium.rate_maps.values() for rate in table.values()),
        *motor.premium.scalars.values(),
    ]
    assert not any(isinstance(value, float) for value in values)
    assert all(isinstance(value, Decimal) for value in values)


def test_rule_set_is_frozen(motor: RuleSet) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        motor.version = 2  # type: ignore[misc]


def test_children_are_frozen(motor: RuleSet) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        motor.premium.base_rate = Decimal("0.99")  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        motor.cancellation.free_look_days = 30  # type: ignore[misc]


def test_rate_maps_are_read_only(motor: RuleSet) -> None:
    with pytest.raises(TypeError):
        motor.premium.rate_maps["zone_rates"]["C"] = Decimal("2.00")  # type: ignore[index]


def test_bands_are_ordered_tuples_and_contain_works(motor: RuleSet) -> None:
    bands = motor.premium.bands["vehicle_age_bands"]
    assert isinstance(bands, tuple)
    assert bands[0].contains(5) and not bands[0].contains(6)
    assert bands[-1].multiplier == Decimal("1.60")


def test_factor_keys_reports_every_factor(motor: RuleSet) -> None:
    assert motor.premium.factor_keys == frozenset(
        {"vehicle_age_bands", "engine_cc_bands", "ncb_discounts", "zone_rates"}
    )


def test_term_life_scalars_and_underwriting() -> None:
    term_life = _rule_set("term_life")
    assert term_life.premium.scalars["smoker_loading"] == Decimal("0.50")
    first = term_life.underwriting.rules[0]
    assert first.when == "age_at_term_end > 75"
    assert first.decision is Decision.DECLINE
    assert first.reason_code == "TL-UW-001"


def test_household_endorsement_and_cancellation() -> None:
    household = _rule_set("household")
    assert EndorsementType.ADD_NOMINEE in household.endorsement.allowed_types
    assert household.cancellation.method is RefundType.PRO_RATA
    assert household.renewal.term_months == 12
    assert household.renewal.grace_period_days == 30


@pytest.mark.parametrize("folder", ["term_life", "motor", "household"])
def test_every_rule_reason_code_is_declared(folder: str) -> None:
    rule_set = _rule_set(folder)
    codes = rule_set.underwriting.reason_codes
    assert all(rule.reason_code in codes for rule in rule_set.underwriting.rules)


def test_money_written_as_a_json_number_is_rejected() -> None:
    data = json.loads((POLICY_RULES / "motor" / "v1.json").read_text(encoding="utf-8"))
    data["premium"]["base_rate"] = 0.031
    with pytest.raises(TypeError):
        RuleSet.from_mapping(data)


def test_invalid_policy_state_exception_carries_the_conventions_envelope() -> None:
    error = InvalidPolicyStateException(
        "Policy is CANCELLED", {"current": "CANCELLED", "target": "ENDORSED"}
    )
    assert isinstance(error, PolicyForgeError)
    assert error.code == "INVALID_POLICY_STATE"
    assert error.http_status == 409
    assert error.details == {"current": "CANCELLED", "target": "ENDORSED"}
