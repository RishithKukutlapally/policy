"""Deterministic premium from a versioned rule set and insured inputs (AC-01, AC-02, NFR-01).

Pure: no I/O, logging or clock. Intermediates stay unrounded `Decimal`; the result is
`max(minimum_premium, raw)` quantized once to 0.01 `ROUND_HALF_UP`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from src.types.enums import ProductCode
from src.types.errors import PremiumFactorNotFoundError, ValidationError
from src.types.rules import PremiumRules, RuleSet

_CENT = Decimal("0.01")
_ONE = Decimal(1)
_AGE_FIELD = {
    ProductCode.TERM_LIFE: "age",
    ProductCode.MOTOR: "owner_age",
    ProductCode.HOUSEHOLD: "proposer_age",
}
_REQUIRED_INPUTS = {
    ProductCode.TERM_LIFE: ("age", "term_years", "smoker"),
    ProductCode.MOTOR: ("owner_age", "vehicle_age_years", "engine_cc", "zone", "ncb_percent"),
    ProductCode.HOUSEHOLD: (
        "proposer_age",
        "construction_type",
        "in_flood_zone",
        "has_security_system",
    ),
}
_FACTOR_KEYS = {
    ProductCode.TERM_LIFE: frozenset({"age_bands", "smoker_loading", "term_years_bands"}),
    ProductCode.MOTOR: frozenset(
        {"vehicle_age_bands", "engine_cc_bands", "ncb_discounts", "zone_rates"}
    ),
    ProductCode.HOUSEHOLD: frozenset(
        {"construction_type_rates", "flood_zone_loading", "security_discount"}
    ),
}


@dataclass(frozen=True, slots=True)
class PremiumStep:
    """One factor applied: its rule-file key and the multiplier used."""

    factor: str
    multiplier: Decimal


@dataclass(frozen=True, slots=True)
class PremiumBreakdown:
    """Full, auditable result of one premium calculation."""

    product: ProductCode
    rule_version: int
    base: Decimal
    steps: tuple[PremiumStep, ...]
    raw_amount: Decimal
    minimum_premium: Decimal
    final_amount: Decimal

    @property
    def factors_used(self) -> tuple[str, ...]:
        """Names of the applied factors, in application order."""
        return tuple(step.factor for step in self.steps)


def _band(rules: PremiumRules, key: str, value: int) -> PremiumStep:
    for band in rules.bands[key]:
        if band.contains(value):
            return PremiumStep(key, band.multiplier)
    raise PremiumFactorNotFoundError(f"no {key} band contains {value}")


def _rate(rules: PremiumRules, key: str, code: str) -> Decimal:
    try:
        return rules.rate_maps[key][code]
    except KeyError:
        raise PremiumFactorNotFoundError(f"no {key} entry for {code!r}") from None


def _term_life(rules: PremiumRules, i: Mapping[str, Any]) -> list[PremiumStep]:
    steps = [_band(rules, "age_bands", i["age"]), _band(rules, "term_years_bands", i["term_years"])]
    if i["smoker"]:
        steps.append(PremiumStep("smoker_loading", _ONE + rules.scalars["smoker_loading"]))
    return steps


def _motor(rules: PremiumRules, i: Mapping[str, Any]) -> list[PremiumStep]:
    discount = _rate(rules, "ncb_discounts", str(i["ncb_percent"]))
    return [
        _band(rules, "vehicle_age_bands", i["vehicle_age_years"]),
        _band(rules, "engine_cc_bands", i["engine_cc"]),
        PremiumStep("zone_rates", _rate(rules, "zone_rates", str(i["zone"]))),
        PremiumStep("ncb_discounts", _ONE - discount),
    ]


def _household(rules: PremiumRules, i: Mapping[str, Any]) -> list[PremiumStep]:
    rate = _rate(rules, "construction_type_rates", str(i["construction_type"]))
    steps = [PremiumStep("construction_type_rates", rate)]
    if i["in_flood_zone"]:
        steps.append(PremiumStep("flood_zone_loading", _ONE + rules.scalars["flood_zone_loading"]))
    if i["has_security_system"]:
        steps.append(PremiumStep("security_discount", _ONE - rules.scalars["security_discount"]))
    return steps


_STRATEGIES: dict[ProductCode, Callable[[PremiumRules, Mapping[str, Any]], list[PremiumStep]]] = {
    ProductCode.TERM_LIFE: _term_life,
    ProductCode.MOTOR: _motor,
    ProductCode.HOUSEHOLD: _household,
}


def _validate(rule_set: RuleSet, inputs: Mapping[str, Any]) -> Decimal:
    """Check factor keys, required inputs and eligibility; return the sum insured."""
    product = rule_set.product
    unknown = rule_set.premium.factor_keys ^ _FACTOR_KEYS[product]
    if unknown:
        raise ValidationError(f"unknown or missing premium factor keys: {sorted(unknown)}")
    missing = [f for f in ("sum_insured", *_REQUIRED_INPUTS[product]) if f not in inputs]
    if missing:
        raise ValidationError(f"missing inputs: {missing}")
    sum_insured = Decimal(str(inputs["sum_insured"]))
    limits = rule_set.eligibility
    age = inputs[_AGE_FIELD[product]]
    if not limits.min_age <= age <= limits.max_age:
        raise ValidationError(f"{_AGE_FIELD[product]} {age} outside eligibility")
    if not limits.min_sum_insured <= sum_insured <= limits.max_sum_insured:
        raise ValidationError(f"sum_insured {sum_insured} outside eligibility")
    return sum_insured


def calculate_premium(rule_set: RuleSet, inputs: Mapping[str, Any]) -> PremiumBreakdown:
    """Premium for `inputs` under `rule_set`; same inputs and version give the same result."""
    sum_insured = _validate(rule_set, inputs)
    rules = rule_set.premium
    base = sum_insured * rules.base_rate
    steps = _STRATEGIES[rule_set.product](rules, inputs)
    raw = base
    for step in steps:
        raw *= step.multiplier
    final = max(rules.minimum_premium, raw).quantize(_CENT, ROUND_HALF_UP)
    return PremiumBreakdown(
        product=rule_set.product,
        rule_version=rule_set.version,
        base=base,
        steps=tuple(steps),
        raw_amount=raw,
        minimum_premium=rules.minimum_premium,
        final_amount=final,
    )
