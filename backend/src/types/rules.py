"""Immutable value objects for a parsed product rule set.

Money and rates are `decimal.Decimal` built from the rule file's JSON strings —
never `float` (NFR-01). Every object is a frozen dataclass; collections are stored
as tuples / read-only mappings so a loaded rule set cannot drift at runtime (NFR-02).
Standard library only: `src.types` imports no framework, logger, clock or I/O.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from src.types.enums import (
    Decision,
    EndorsementType,
    ProductCode,
    RefundType,
    RuleSetStatus,
)

BAND_KEYS = ("min", "max", "multiplier")


@dataclass(frozen=True, slots=True)
class Band:
    """One inclusive `min`–`max` band and its premium multiplier."""

    min: int
    max: int
    multiplier: Decimal

    def contains(self, value: int) -> bool:
        """True when `value` falls inside this band (both bounds inclusive)."""
        return self.min <= value <= self.max


@dataclass(frozen=True, slots=True)
class PremiumRules:
    """Base rate, floor premium and the product's rating factors (AC-01)."""

    base_rate: Decimal
    minimum_premium: Decimal
    bands: Mapping[str, tuple[Band, ...]]
    rate_maps: Mapping[str, Mapping[str, Decimal]]
    scalars: Mapping[str, Decimal]

    @property
    def factor_keys(self) -> frozenset[str]:
        """Every `premium.factors` key, whatever its shape."""
        return frozenset((*self.bands, *self.rate_maps, *self.scalars))


@dataclass(frozen=True, slots=True)
class Eligibility:
    """Age and sum-insured bounds a risk must satisfy (AC-03)."""

    min_age: int
    max_age: int
    min_sum_insured: Decimal
    max_sum_insured: Decimal


@dataclass(frozen=True, slots=True)
class UnderwritingRule:
    """One `when → decision` rule with its reason code (AC-04)."""

    when: str
    decision: Decision
    reason_code: str


@dataclass(frozen=True, slots=True)
class UnderwritingRules:
    """Ordered automatic rules plus the product's reason-code dictionary."""

    rules: tuple[UnderwritingRule, ...]
    reason_codes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class EndorsementRules:
    """Endorsement types this version permits (AC-16)."""

    allowed_types: frozenset[EndorsementType]


@dataclass(frozen=True, slots=True)
class RenewalRules:
    """Term length and grace period in days (AC-07)."""

    term_months: int
    grace_period_days: int


@dataclass(frozen=True, slots=True)
class CancellationRules:
    """Refund method, free-look window and the flat admin fee (AC-08)."""

    method: RefundType
    free_look_days: int
    admin_fee: Decimal


def _decimal(value: str) -> Decimal:
    """Build a `Decimal` from a rule-file money/rate string, rejecting JSON numbers."""
    if not isinstance(value, str):
        raise TypeError(f"money and rate values must be JSON strings, got {type(value).__name__}")
    return Decimal(value)


def _band(node: Mapping[str, Any]) -> Band:
    """Build one `Band` from a `{min, max, multiplier}` node."""
    return Band(min=int(node["min"]), max=int(node["max"]), multiplier=_decimal(node["multiplier"]))


def _premium_rules(node: Mapping[str, Any]) -> PremiumRules:
    """Split `premium.factors` into band tables, rate maps and scalar loadings."""
    bands: dict[str, tuple[Band, ...]] = {}
    rate_maps: dict[str, Mapping[str, Decimal]] = {}
    scalars: dict[str, Decimal] = {}
    for key, factor in node["factors"].items():
        if isinstance(factor, list):
            bands[key] = tuple(_band(item) for item in factor)
        elif isinstance(factor, dict):
            rate_maps[key] = MappingProxyType({k: _decimal(v) for k, v in factor.items()})
        else:
            scalars[key] = _decimal(factor)
    return PremiumRules(
        base_rate=_decimal(node["base_rate"]),
        minimum_premium=_decimal(node["minimum_premium"]),
        bands=MappingProxyType(bands),
        rate_maps=MappingProxyType(rate_maps),
        scalars=MappingProxyType(scalars),
    )


def _eligibility(node: Mapping[str, Any]) -> Eligibility:
    """Build `Eligibility` from the `eligibility` node."""
    return Eligibility(
        min_age=int(node["min_age"]),
        max_age=int(node["max_age"]),
        min_sum_insured=_decimal(node["min_sum_insured"]),
        max_sum_insured=_decimal(node["max_sum_insured"]),
    )


def _underwriting(node: Mapping[str, Any]) -> UnderwritingRules:
    """Build `UnderwritingRules` from the `underwriting` node."""
    rules = tuple(
        UnderwritingRule(
            when=rule["when"],
            decision=Decision(rule["decision"]),
            reason_code=rule["reason_code"],
        )
        for rule in node["rules"]
    )
    return UnderwritingRules(rules=rules, reason_codes=MappingProxyType(dict(node["reason_codes"])))


@dataclass(frozen=True, slots=True)
class RuleSet:
    """A whole versioned product rule set, exactly as published (AC-02)."""

    product: ProductCode
    version: int
    status: RuleSetStatus
    effective_from: date
    currency: str
    premium: PremiumRules
    eligibility: Eligibility
    underwriting: UnderwritingRules
    endorsement: EndorsementRules
    renewal: RenewalRules
    cancellation: CancellationRules

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RuleSet":
        """Build a rule set from already schema-validated rule-file JSON."""
        cancellation = data["cancellation"]
        return cls(
            product=ProductCode(data["product"]),
            version=int(data["version"]),
            status=RuleSetStatus(data["status"]),
            effective_from=date.fromisoformat(data["effective_from"]),
            currency=data["currency"],
            premium=_premium_rules(data["premium"]),
            eligibility=_eligibility(data["eligibility"]),
            underwriting=_underwriting(data["underwriting"]),
            endorsement=EndorsementRules(
                allowed_types=frozenset(
                    EndorsementType(t) for t in data["endorsement"]["allowed_types"]
                )
            ),
            renewal=RenewalRules(
                term_months=int(data["renewal"]["term_months"]),
                grace_period_days=int(data["renewal"]["grace_period_days"]),
            ),
            cancellation=CancellationRules(
                method=RefundType(cancellation["method"]),
                free_look_days=int(cancellation["free_look_days"]),
                admin_fee=_decimal(cancellation["admin_fee"]),
            ),
        )
