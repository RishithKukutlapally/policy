"""Unit tests for pure term-day maths, including leap years."""

from __future__ import annotations

from datetime import date

import pytest

from src.domain.term_days import days_elapsed, term_days, unused_days
from src.types.errors import ValidationError


def test_term_days_common_year() -> None:
    assert term_days(date(2026, 1, 1), date(2026, 12, 31)) == 365


def test_term_days_leap_year() -> None:
    assert term_days(date(2028, 1, 1), date(2028, 12, 31)) == 366


def test_term_days_leap_day_spanning_twelve_months() -> None:
    assert term_days(date(2027, 3, 1), date(2028, 2, 29)) == 366


def test_term_days_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError):
        term_days(date(2026, 2, 1), date(2026, 1, 1))


def test_days_elapsed_and_unused() -> None:
    start, end = date(2026, 1, 1), date(2026, 12, 31)
    assert days_elapsed(start, date(2026, 1, 31)) == 30
    assert unused_days(start, end, date(2026, 1, 31)) == 335
    assert unused_days(start, end, start) == 365


def test_unused_days_clamped() -> None:
    start, end = date(2026, 1, 1), date(2026, 12, 31)
    assert unused_days(start, end, date(2027, 6, 1)) == 0
    assert unused_days(start, end, date(2025, 12, 1)) == 365


def test_unused_days_leap_year() -> None:
    assert unused_days(date(2028, 1, 1), date(2028, 12, 31), date(2028, 3, 1)) == 366 - 60
