"""Unit tests for pure renewal rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.domain.renewal_rules import (
    PolicyView,
    end_of_day_action,
    renewal_premium,
    renewal_schedule,
)
from src.types.enums import EndOfDayAction, PolicyStatus
from src.types.rules import RuleSet

_RULES = Path(__file__).resolve().parents[2] / "policy_rules"


def _rs(folder: str) -> RuleSet:
    data: dict[str, Any] = json.loads((_RULES / folder / "v1.json").read_text(encoding="utf-8"))
    return RuleSet.from_mapping(data)


def test_schedule_leap_year_term() -> None:
    s = renewal_schedule(_rs("motor"), date(2027, 2, 28))
    assert (s.effective_date, s.expiry_date) == (date(2027, 3, 1), date(2028, 2, 29))


def test_schedule_from_leap_day_expiry() -> None:
    s = renewal_schedule(_rs("motor"), date(2028, 2, 29))
    assert (s.effective_date, s.expiry_date) == (date(2028, 3, 1), date(2029, 2, 28))


def test_action_before_default_window_is_none() -> None:
    v = PolicyView(PolicyStatus.ACTIVE, date(2027, 1, 14), True)
    assert end_of_day_action(v, date(2026, 12, 1), _rs("motor")) is EndOfDayAction.NONE


def test_household_premium_is_two_dp_decimal() -> None:
    inputs = {
        "sum_insured": "1000000.00",
        "proposer_age": 40,
        "construction_type": "BRICK",
        "in_flood_zone": True,
        "has_security_system": False,
    }
    p = renewal_premium(_rs("household"), inputs)
    assert isinstance(p, Decimal)
    assert p.as_tuple().exponent == -2
