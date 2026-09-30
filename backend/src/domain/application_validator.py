"""Pure application validation against the active rule set (AC-03).

Findings carry only a field path and a canonical detail code, never an input value
(NFR-03). No logging, I/O or clock: age is supplied by the caller.
"""

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from src.types.enums import ProductCode
from src.types.rules import RuleSet

REQUIRED = "REQUIRED"
OUT_OF_RANGE = "OUT_OF_RANGE"
INVALID_FORMAT = "INVALID_FORMAT"

_AADHAAR = re.compile(r"^\d{12}$")
_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

_AGE_FIELD: Mapping[ProductCode, str] = {
    ProductCode.TERM_LIFE: "age",
    ProductCode.MOTOR: "owner_age",
    ProductCode.HOUSEHOLD: "proposer_age",
}
_INT_FIELDS: Mapping[ProductCode, tuple[str, ...]] = {
    ProductCode.TERM_LIFE: ("term_years",),
    ProductCode.MOTOR: ("vehicle_age_years", "engine_cc"),
    ProductCode.HOUSEHOLD: (),
}
_BOOL_FIELDS: Mapping[ProductCode, tuple[str, ...]] = {
    ProductCode.TERM_LIFE: ("smoker",),
    ProductCode.MOTOR: (),
    ProductCode.HOUSEHOLD: ("in_flood_zone", "has_security_system"),
}
_ENUM_FIELDS: Mapping[ProductCode, Mapping[str, frozenset[str]]] = {
    ProductCode.TERM_LIFE: {},
    ProductCode.MOTOR: {"zone": frozenset({"A", "B"})},
    ProductCode.HOUSEHOLD: {
        "construction_type": frozenset({"CONCRETE", "BRICK", "TIMBER", "THATCH"})
    },
}
_INT_MINIMUM: Mapping[str, int] = {"vehicle_age_years": 0, "engine_cc": 1, "term_years": 1}


class FieldError(NamedTuple):
    """One failing field: dotted path and canonical detail code."""

    field: str
    code: str


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _validate_kyc(kyc: Mapping[str, Any]) -> list[FieldError]:
    errors: list[FieldError] = []
    for name in ("full_name", "address", "date_of_birth", "aadhaar", "pan"):
        if _blank(kyc.get(name)):
            errors.append(FieldError(f"kyc.{name}", REQUIRED))
    for name, pattern in (("aadhaar", _AADHAAR), ("pan", _PAN)):
        value = kyc.get(name)
        if not _blank(value) and not (isinstance(value, str) and pattern.match(value)):
            errors.append(FieldError(f"kyc.{name}", INVALID_FORMAT))
    dob = kyc.get("date_of_birth")
    if not _blank(dob):
        try:
            date.fromisoformat(str(dob))
        except ValueError:
            errors.append(FieldError("kyc.date_of_birth", INVALID_FORMAT))
    return errors


def _validate_sum_insured(rule_set: RuleSet, risk: Mapping[str, Any]) -> list[FieldError]:
    value = risk.get("sum_insured")
    if _blank(value):
        return [FieldError("sum_insured", REQUIRED)]
    if isinstance(value, bool | float):
        return [FieldError("sum_insured", INVALID_FORMAT)]
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return [FieldError("sum_insured", INVALID_FORMAT)]
    if not amount.is_finite():
        return [FieldError("sum_insured", INVALID_FORMAT)]
    limits = rule_set.eligibility
    if not limits.min_sum_insured <= amount <= limits.max_sum_insured:
        return [FieldError("sum_insured", OUT_OF_RANGE)]
    return []


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_ints(rule_set: RuleSet, risk: Mapping[str, Any]) -> list[FieldError]:
    product = rule_set.product
    age_field = _AGE_FIELD[product]
    limits = rule_set.eligibility
    errors: list[FieldError] = []
    for name in (age_field, *_INT_FIELDS[product]):
        value = risk.get(name)
        if value is None:
            errors.append(FieldError(name, REQUIRED))
        elif not _is_int(value):
            errors.append(FieldError(name, INVALID_FORMAT))
        elif name == age_field:
            if not limits.min_age <= value <= limits.max_age:
                errors.append(FieldError(name, OUT_OF_RANGE))
        elif value < _INT_MINIMUM[name]:
            errors.append(FieldError(name, OUT_OF_RANGE))
    return errors


def _validate_flags_and_enums(rule_set: RuleSet, risk: Mapping[str, Any]) -> list[FieldError]:
    product = rule_set.product
    errors: list[FieldError] = []
    for name in _BOOL_FIELDS[product]:
        value = risk.get(name)
        if value is None:
            errors.append(FieldError(name, REQUIRED))
        elif not isinstance(value, bool):
            errors.append(FieldError(name, INVALID_FORMAT))
    for name, allowed in _ENUM_FIELDS[product].items():
        value = risk.get(name)
        if _blank(value):
            errors.append(FieldError(name, REQUIRED))
        elif value not in allowed:
            errors.append(FieldError(name, INVALID_FORMAT))
    if product is ProductCode.MOTOR:
        ncb = risk.get("ncb_percent")
        if _blank(ncb):
            errors.append(FieldError("ncb_percent", REQUIRED))
        elif str(ncb) not in rule_set.premium.rate_maps.get("ncb_discounts", {}):
            errors.append(FieldError("ncb_percent", INVALID_FORMAT))
    return errors


def _validate_health(rule_set: RuleSet, health: Mapping[str, Any] | None) -> list[FieldError]:
    if rule_set.product is not ProductCode.TERM_LIFE:
        return []
    if not health:
        return [FieldError("health_declaration", REQUIRED)]
    if not isinstance(health.get("has_pre_existing_condition"), bool):
        return [FieldError("health_declaration.has_pre_existing_condition", REQUIRED)]
    return []


def validate_application(
    rule_set: RuleSet,
    kyc: Mapping[str, Any],
    risk: Mapping[str, Any],
    health_declaration: Mapping[str, Any] | None = None,
) -> list[FieldError]:
    """All failing fields at once; an empty list means the application is valid.

    A `health_declaration` key inside `risk` is used when the argument is omitted.
    """
    health = (
        health_declaration if health_declaration is not None else risk.get("health_declaration")
    )
    return [
        *_validate_kyc(kyc),
        *_validate_ints(rule_set, risk),
        *_validate_flags_and_enums(rule_set, risk),
        *_validate_sum_insured(rule_set, risk),
        *_validate_health(rule_set, health),
    ]


def kyc_status(errors: list[FieldError]) -> str:
    """KYC stub status: `VERIFIED` when no `kyc.*` finding exists, else `REJECTED`."""
    return "REJECTED" if any(e.field.startswith("kyc.") for e in errors) else "VERIFIED"
