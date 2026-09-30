"""Boundary and precision cases for `src.domain.endorsement_rules` (AC-16, NFR-01)."""

from decimal import Decimal
from typing import Any

import pytest

from src.config.rule_loader import load_rule_file
from src.domain.endorsement_rules import EndorsementOutcome, build_outcome, premium_delta
from src.types.enums import EndorsementType, ProductCode
from src.types.errors import ValidationError

_MOTOR = load_rule_file(ProductCode.MOTOR, 1)


def _motor(sum_insured: str) -> dict[str, Any]:
    return {
        "sum_insured": Decimal(sum_insured),
        "owner_age": 30,
        "vehicle_age_years": 2,
        "engine_cc": 998,
        "zone": "B",
        "ncb_percent": "0",
    }


def test_zero_unused_days_gives_zero() -> None:
    delta = premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), 0, 365)
    assert delta == Decimal("0.00")
    assert delta.as_tuple().exponent == -2


def test_full_term_gives_full_premium_difference() -> None:
    delta = premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), 365, 365)
    assert delta == Decimal("3100.00")


def test_leap_year_term_uses_366_days() -> None:
    delta = premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), 183, 366)
    assert delta == Decimal("1550.00")


def test_no_intermediate_rounding() -> None:
    # Rounding the per-day rate first (3100/365 -> 8.49) would give 1553.67.
    delta = premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), 183, 365)
    assert delta == Decimal("1554.25")
    assert delta != Decimal("1553.67")


def test_half_cent_rounds_up() -> None:
    # 3100 * 1 / 800 = 3.875 exactly -> 3.88 under ROUND_HALF_UP.
    delta = premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), 1, 800)
    assert delta == Decimal("3.88")


@pytest.mark.parametrize(("unused", "term"), [(-1, 365), (10, 0), (400, 365)])
def test_invalid_day_counts_rejected(unused: int, term: int) -> None:
    with pytest.raises(ValidationError):
        premium_delta(_MOTOR, _motor("400000.00"), _motor("500000.00"), unused, term)


def test_outcome_is_frozen_and_carries_rule_version() -> None:
    outcome = build_outcome(
        _MOTOR,
        EndorsementType.CHANGE_SUM_INSURED,
        _motor("400000.00"),
        _motor("500000.00"),
        183,
        365,
    )
    assert isinstance(outcome, EndorsementOutcome)
    assert outcome.premium_delta == Decimal("1554.25")
    assert outcome.rule_version == 1
    assert outcome.changes == {"sum_insured": Decimal("500000.00")}
    with pytest.raises(AttributeError):
        outcome.premium_delta = Decimal("0.00")  # type: ignore[misc]


def test_outcome_for_address_is_zero() -> None:
    outcome = build_outcome(
        _MOTOR,
        EndorsementType.CHANGE_ADDRESS,
        _motor("400000.00"),
        {**_motor("400000.00"), "address": "2 New Road"},
        183,
        365,
    )
    assert outcome.premium_delta == Decimal("0.00")
    assert outcome.changes == {"address": "2 New Road"}
