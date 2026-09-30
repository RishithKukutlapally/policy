"""AC-07: renewal schedule, end-of-day action and refreshed premium on the real v1 rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.domain.renewal_rules import (
    PolicyView,
    end_of_day_action,
    is_in_renewal_window,
    renewal_premium,
    renewal_schedule,
)
from src.types.enums import EndOfDayAction, PolicyStatus
from src.types.rules import RuleSet

RULES = Path(__file__).resolve().parents[2] / "policy_rules"
EXPIRY = date(2027, 1, 14)


def _rs(folder: str) -> RuleSet:
    data: dict[str, Any] = json.loads((RULES / folder / "v1.json").read_text(encoding="utf-8"))
    return RuleSet.from_mapping(data)


def _view(paid: bool, status: PolicyStatus = PolicyStatus.ACTIVE) -> PolicyView:
    return PolicyView(status=status, expiry_date=EXPIRY, renewal_paid=paid)


@pytest.mark.ac("AC-07")
def test_ac07_schedule_due_and_grace_end() -> None:
    s = renewal_schedule(_rs("motor"), EXPIRY)
    assert s.effective_date == date(2027, 1, 15)
    assert s.expiry_date == date(2028, 1, 14)
    assert s.due_date == date(2027, 1, 15)
    assert s.grace_end == date(2027, 2, 14)


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize(
    ("as_of", "paid", "expected"),
    [
        (date(2026, 12, 1), False, EndOfDayAction.NONE),
        (date(2027, 1, 14), False, EndOfDayAction.NONE),
        (date(2027, 1, 15), False, EndOfDayAction.IN_GRACE),
        (date(2027, 2, 14), False, EndOfDayAction.IN_GRACE),
        (date(2027, 2, 15), False, EndOfDayAction.LAPSE),
        (date(2027, 1, 15), True, EndOfDayAction.RENEW),
        (date(2027, 3, 1), True, EndOfDayAction.RENEW),
    ],
)
def test_ac07_end_of_day_action(as_of: date, paid: bool, expected: EndOfDayAction) -> None:
    assert end_of_day_action(_view(paid), as_of, _rs("motor")) is expected


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize(
    "status", [PolicyStatus.LAPSED, PolicyStatus.CANCELLED, PolicyStatus.RENEWED]
)
def test_ac07_terminal_statuses_give_none(status: PolicyStatus) -> None:
    result = end_of_day_action(_view(False, status), date(2027, 3, 1), _rs("motor"))
    assert result is EndOfDayAction.NONE


@pytest.mark.ac("AC-07")
def test_ac07_endorsed_behaves_like_active() -> None:
    v = _view(False, PolicyStatus.ENDORSED)
    assert end_of_day_action(v, date(2027, 2, 15), _rs("motor")) is EndOfDayAction.LAPSE


@pytest.mark.ac("AC-07")
def test_ac07_renewal_window() -> None:
    assert not is_in_renewal_window(EXPIRY, date(2026, 12, 14), 30)
    assert is_in_renewal_window(EXPIRY, date(2026, 12, 15), 30)


@pytest.mark.ac("AC-07")
def test_ac07_renewal_premium_recomputed_on_advanced_age_band() -> None:
    inputs = {
        "sum_insured": "400000.00",
        "owner_age": 35,
        "vehicle_age_years": 6,
        "engine_cc": 1000,
        "zone": "B",
        "ncb_percent": "0",
    }
    # 6 is in the 1.15 band: 400000 * 0.0310 * 1.15 on v1 (spec's 14720.00 is a v2 figure)
    assert renewal_premium(_rs("motor"), inputs) == Decimal("14260.00")
