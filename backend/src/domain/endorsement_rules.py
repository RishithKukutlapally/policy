"""Pure endorsement rules: type/eligibility validation and pro-rated premium delta (AC-16, NFR-01).

No I/O, logging or clock. The delta is `(new - old) * unused_days / term_days` on the policy's own
rule version, quantized once at the end to 0.01 `ROUND_HALF_UP`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any

from src.domain.premium_calculator import calculate_premium
from src.types.enums import EndorsementType
from src.types.errors import ValidationError
from src.types.rules import RuleSet

Finding = tuple[str, str]

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal(100)
_REQUIRED_FIELDS: dict[EndorsementType, tuple[str, ...]] = {
    EndorsementType.CHANGE_ADDRESS: ("address",),
    EndorsementType.ADD_NOMINEE: ("nominee_name", "relationship"),
    EndorsementType.CHANGE_SUM_INSURED: ("new_sum_insured",),
}
_CHANGE_FIELDS: dict[EndorsementType, tuple[str, ...]] = {
    EndorsementType.CHANGE_ADDRESS: ("address",),
    EndorsementType.ADD_NOMINEE: ("nominee_name", "relationship", "share_percent"),
    EndorsementType.CHANGE_SUM_INSURED: ("sum_insured",),
}


@dataclass(frozen=True, slots=True)
class EndorsementOutcome:
    """A validated endorsement: what changes, the premium delta and the rule version used."""

    endorsement_type: EndorsementType
    changes: Mapping[str, Any]
    premium_delta: Decimal
    rule_version: int


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _validate_sum_insured(
    rule_set: RuleSet, current: Mapping[str, Any], requested: Mapping[str, Any]
) -> list[Finding]:
    new = _decimal(requested["new_sum_insured"])
    if new is None:
        return [("new_sum_insured", "REQUIRED")]
    limits = rule_set.eligibility
    if not limits.min_sum_insured <= new <= limits.max_sum_insured:
        return [("new_sum_insured", "OUT_OF_RANGE")]
    if "sum_insured" in current and _decimal(current["sum_insured"]) == new:
        return [("new_sum_insured", "UNCHANGED")]
    return []


def _validate_nominee(current: Mapping[str, Any], requested: Mapping[str, Any]) -> list[Finding]:
    share = _decimal(requested.get("share_percent", 0))
    existing = _decimal(current.get("nominee_share_total", 0))
    if share is None or existing is None or existing + share > _HUNDRED:
        return [("share_percent", "SHARE_EXCEEDS_100")]
    return []


def validate_endorsement(
    rule_set: RuleSet,
    endorsement_type: EndorsementType,
    current: Mapping[str, Any],
    requested: Mapping[str, Any],
) -> list[Finding]:
    """Return `(field_path, detail_code)` findings; an empty list means the request is valid."""
    if endorsement_type not in rule_set.endorsement.allowed_types:
        return [("endorsement_type", "NOT_ALLOWED")]
    missing = [
        (name, "REQUIRED")
        for name in _REQUIRED_FIELDS[endorsement_type]
        if _blank(requested.get(name))
    ]
    if missing:
        return missing
    if endorsement_type is EndorsementType.CHANGE_SUM_INSURED:
        return _validate_sum_insured(rule_set, current, requested)
    if endorsement_type is EndorsementType.ADD_NOMINEE:
        return _validate_nominee(current, requested)
    return []


def premium_delta(
    rule_set: RuleSet,
    current_inputs: Mapping[str, Any],
    new_inputs: Mapping[str, Any],
    unused_days: int,
    term_days: int,
    endorsement_type: EndorsementType = EndorsementType.CHANGE_SUM_INSURED,
) -> Decimal:
    """Pro-rated premium delta; exactly `0.00` for non-priced endorsement types."""
    if endorsement_type is not EndorsementType.CHANGE_SUM_INSURED:
        return _ZERO
    if term_days <= 0 or not 0 <= unused_days <= term_days:
        raise ValidationError("unused_days must be within 0..term_days and term_days positive")
    old = calculate_premium(rule_set, current_inputs).final_amount
    new = calculate_premium(rule_set, new_inputs).final_amount
    return ((new - old) * unused_days / term_days).quantize(_CENT, ROUND_HALF_UP)


def build_outcome(
    rule_set: RuleSet,
    endorsement_type: EndorsementType,
    current_inputs: Mapping[str, Any],
    new_inputs: Mapping[str, Any],
    unused_days: int,
    term_days: int,
) -> EndorsementOutcome:
    """Bundle the changed fields, premium delta and rule version of one endorsement."""
    changes = {k: new_inputs[k] for k in _CHANGE_FIELDS[endorsement_type] if k in new_inputs}
    delta = premium_delta(
        rule_set, current_inputs, new_inputs, unused_days, term_days, endorsement_type
    )
    return EndorsementOutcome(
        endorsement_type=endorsement_type,
        changes=MappingProxyType(changes),
        premium_delta=delta,
        rule_version=rule_set.version,
    )
