"""Renewal term, grace period and end-of-day action rules (AC-07, NFR-01).

Pure: every date is passed in; no I/O, logging or clock.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from src.domain.premium_calculator import calculate_premium
from src.types.enums import EndOfDayAction, PolicyStatus
from src.types.rules import RuleSet

DEFAULT_RENEWAL_WINDOW_DAYS = 30
_ACTIONABLE = frozenset({PolicyStatus.ACTIVE, PolicyStatus.ENDORSED})


@dataclass(frozen=True, slots=True)
class PolicyView:
    """The policy facts the end-of-day decision needs."""

    status: PolicyStatus
    expiry_date: date
    renewal_paid: bool


@dataclass(frozen=True, slots=True)
class RenewalSchedule:
    """Dates of the next term and its premium due / grace end."""

    effective_date: date
    expiry_date: date
    due_date: date
    grace_end: date


def _add_months(start: date, months: int) -> date:
    """`start` plus whole months, clamping the day to the target month's length."""
    index = start.year * 12 + (start.month - 1) + months
    year, m0 = divmod(index, 12)
    first_next = date(year + (m0 == 11), (m0 + 1) % 12 + 1, 1)
    last_day = (first_next - timedelta(days=1)).day
    return date(year, m0 + 1, min(start.day, last_day))


def renewal_schedule(rule_set: RuleSet, expiry_date: date) -> RenewalSchedule:
    """Next term starts the day after `expiry_date`; premium is due on that day."""
    effective = expiry_date + timedelta(days=1)
    new_expiry = _add_months(effective, rule_set.renewal.term_months) - timedelta(days=1)
    grace_end = effective + timedelta(days=rule_set.renewal.grace_period_days)
    return RenewalSchedule(effective, new_expiry, effective, grace_end)


def renewal_premium(rule_set: RuleSet, inputs: Mapping[str, Any]) -> Decimal:
    """Refreshed premium on the given (active) rule version; quantized once by the calculator."""
    return calculate_premium(rule_set, inputs).final_amount


def is_in_renewal_window(expiry_date: date, as_of: date, renewal_window_days: int) -> bool:
    """True from `expiry_date - renewal_window_days` onward."""
    return as_of >= expiry_date - timedelta(days=renewal_window_days)


def end_of_day_action(
    policy: PolicyView,
    as_of: date,
    rule_set: RuleSet,
    renewal_window_days: int = DEFAULT_RENEWAL_WINDOW_DAYS,
) -> EndOfDayAction:
    """Decide what the end-of-day job does with `policy` on `as_of`."""
    if policy.status not in _ACTIONABLE:
        return EndOfDayAction.NONE
    schedule = renewal_schedule(rule_set, policy.expiry_date)
    if not is_in_renewal_window(policy.expiry_date, as_of, renewal_window_days):
        return EndOfDayAction.NONE
    if policy.renewal_paid:
        return EndOfDayAction.RENEW if as_of >= schedule.due_date else EndOfDayAction.NONE
    if as_of < schedule.due_date:
        return EndOfDayAction.NONE
    return EndOfDayAction.IN_GRACE if as_of <= schedule.grace_end else EndOfDayAction.LAPSE
