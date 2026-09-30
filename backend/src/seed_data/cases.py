"""The synthetic quote/application cases the seed submits (AC-04, success metric M3).

Each case is shaped so the *real* underwriting rules of ``policy_rules/<product>/v1.json`` reach
the ``expected`` decision — the seed asserts nothing, it simply chooses inputs whose outcome is
known: 21 clean cases auto-bind, 3 trip a MANUAL_REVIEW rule and 1 trips a DECLINE rule, giving
84 % auto-bind. Money is a decimal **string**; the services parse it to ``Decimal``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from src.types.enums import Decision, ProductCode

#: Fictional address shared by every synthetic applicant.
ADDRESS_TEMPLATE: Final = "{number} Sample Street, Testville 560001"
#: How many distinct demo customers the cases are spread over (``cust-001`` … ``cust-005``).
CUSTOMER_COUNT: Final = 5


@dataclass(frozen=True, slots=True)
class SeedCase:
    """One quote + application the seed submits, and the decision its inputs must produce."""

    product: ProductCode
    inputs: dict[str, Any]
    expected: Decision
    health_declaration: dict[str, Any] | None = None
    #: Label of the lifecycle policy this case backs, or ``""`` for an ordinary demo case.
    lifecycle: str = ""
    nominees: tuple[str, ...] = field(default=())


def kyc_for(index: int) -> dict[str, Any]:
    """Synthetic KYC for ``Test Customer NN`` — Aadhaar ``9999…``, PAN ``AAAAA000NA``."""
    return {
        "full_name": f"Test Customer {index:02d}",
        "date_of_birth": f"{1990 - index % 20:04d}-04-{(index % 27) + 1:02d}",
        "aadhaar": f"9999{index:08d}",
        "pan": f"AAAAA{index:04d}A",
        "address": ADDRESS_TEMPLATE.format(number=index),
    }


def _term_life(
    sum_insured: str, age: int, term_years: int, *, smoker: bool = False
) -> dict[str, Any]:
    return {
        "sum_insured": sum_insured,
        "age": age,
        "term_years": term_years,
        "smoker": smoker,
    }


def _motor(
    sum_insured: str, owner_age: int, vehicle_age_years: int, engine_cc: int, ncb: str
) -> dict[str, Any]:
    return {
        "sum_insured": sum_insured,
        "owner_age": owner_age,
        "vehicle_age_years": vehicle_age_years,
        "engine_cc": engine_cc,
        "zone": "A" if owner_age % 2 else "B",
        "ncb_percent": ncb,
    }


def _household(
    sum_insured: str,
    proposer_age: int,
    construction: str,
    *,
    flood: bool = False,
    security: bool = True,
) -> dict[str, Any]:
    return {
        "sum_insured": sum_insured,
        "proposer_age": proposer_age,
        "construction_type": construction,
        "in_flood_zone": flood,
        "has_security_system": security,
    }


_HEALTHY: Final[dict[str, Any]] = {"has_pre_existing_condition": False, "details": ""}
_CONDITION: Final[dict[str, Any]] = {
    "has_pre_existing_condition": True,
    "details": "Synthetic sample condition",
}

#: The five policies that carry the lifecycle showcase (ACTIVE ×2, ENDORSED, RENEWED, LAPSED,
#: CANCELLED). ``lifecycle`` labels are consumed by :mod:`src.seed_data.portfolio`.
LIFECYCLE_CASES: Final[tuple[SeedCase, ...]] = (
    SeedCase(
        ProductCode.HOUSEHOLD,
        _household("2500000.00", 44, "BRICK"),
        Decision.AUTO_BIND,
        lifecycle="lapse",
    ),
    SeedCase(
        ProductCode.MOTOR,
        _motor("900000.00", 38, 3, 1400, "25"),
        Decision.AUTO_BIND,
        lifecycle="renewal",
    ),
    SeedCase(
        ProductCode.MOTOR,
        _motor("750000.00", 41, 2, 1200, "20"),
        Decision.AUTO_BIND,
        lifecycle="active",
    ),
    SeedCase(
        ProductCode.HOUSEHOLD,
        _household("3200000.00", 36, "CONCRETE"),
        Decision.AUTO_BIND,
        lifecycle="active",
    ),
    SeedCase(
        ProductCode.TERM_LIFE,
        _term_life("4000000.00", 34, 20),
        Decision.AUTO_BIND,
        health_declaration=_HEALTHY,
        lifecycle="endorse",
    ),
    SeedCase(
        ProductCode.MOTOR,
        _motor("600000.00", 29, 1, 998, "0"),
        Decision.AUTO_BIND,
        lifecycle="cancel",
    ),
)

#: Ordinary demo cases: clean ones stay ``AUTO_BIND`` and ready to issue, the rest populate the
#: underwriting workbench (``MANUAL_REVIEW``) and the admin override screen (``DECLINE``).
_EXTRA_CASES: Final[tuple[SeedCase, ...]] = (
    SeedCase(ProductCode.TERM_LIFE, _term_life("1500000.00", 27, 15), Decision.AUTO_BIND, _HEALTHY),
    SeedCase(ProductCode.TERM_LIFE, _term_life("2500000.00", 31, 10), Decision.AUTO_BIND, _HEALTHY),
    SeedCase(
        ProductCode.TERM_LIFE,
        _term_life("5000000.00", 45, 12, smoker=True),
        Decision.AUTO_BIND,
        _HEALTHY,
    ),
    SeedCase(ProductCode.TERM_LIFE, _term_life("8000000.00", 52, 8), Decision.AUTO_BIND, _HEALTHY),
    SeedCase(ProductCode.TERM_LIFE, _term_life("900000.00", 23, 30), Decision.AUTO_BIND, _HEALTHY),
    SeedCase(ProductCode.MOTOR, _motor("450000.00", 33, 5, 1600, "35"), Decision.AUTO_BIND),
    SeedCase(ProductCode.MOTOR, _motor("1200000.00", 47, 8, 2000, "45"), Decision.AUTO_BIND),
    SeedCase(ProductCode.MOTOR, _motor("300000.00", 55, 9, 800, "50"), Decision.AUTO_BIND),
    SeedCase(ProductCode.MOTOR, _motor("2000000.00", 26, 0, 1498, "0"), Decision.AUTO_BIND),
    SeedCase(ProductCode.MOTOR, _motor("1750000.00", 61, 6, 1100, "20"), Decision.AUTO_BIND),
    SeedCase(ProductCode.HOUSEHOLD, _household("800000.00", 30, "CONCRETE"), Decision.AUTO_BIND),
    SeedCase(
        ProductCode.HOUSEHOLD,
        _household("1500000.00", 49, "TIMBER", security=False),
        Decision.AUTO_BIND,
    ),
    SeedCase(
        ProductCode.HOUSEHOLD, _household("4500000.00", 58, "BRICK", flood=True), Decision.AUTO_BIND
    ),
    SeedCase(ProductCode.HOUSEHOLD, _household("6500000.00", 39, "CONCRETE"), Decision.AUTO_BIND),
    SeedCase(ProductCode.HOUSEHOLD, _household("950000.00", 66, "BRICK"), Decision.AUTO_BIND),
    # MO-UW-002: a vehicle older than 10 years goes to the workbench.
    SeedCase(ProductCode.MOTOR, _motor("400000.00", 43, 12, 1300, "0"), Decision.MANUAL_REVIEW),
    # HH-UW-002: a high sum insured inside a flood zone goes to the workbench.
    SeedCase(
        ProductCode.HOUSEHOLD,
        _household("9000000.00", 37, "BRICK", flood=True),
        Decision.MANUAL_REVIEW,
    ),
    # TL-UW-003: a declared pre-existing condition goes to the workbench.
    SeedCase(
        ProductCode.TERM_LIFE,
        _term_life("3000000.00", 48, 15),
        Decision.MANUAL_REVIEW,
        _CONDITION,
    ),
    # TL-UW-001: age at end of term above 75 is declined and waits for an admin override.
    SeedCase(ProductCode.TERM_LIFE, _term_life("2000000.00", 59, 20), Decision.DECLINE, _HEALTHY),
)

#: Every case the seed submits, lifecycle showcase first.
CASES: Final[tuple[SeedCase, ...]] = LIFECYCLE_CASES + _EXTRA_CASES
