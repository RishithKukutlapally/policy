"""Term arithmetic behind ``expiry_date = effective_date + term_months - 1 day`` (AC-05)."""

from __future__ import annotations

from datetime import date

import pytest

from src.service.policy_service import add_months, term_end


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 3, 1), 12, date(2027, 3, 1)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2026, 12, 15), 12, date(2027, 12, 15)),
        (date(2027, 1, 31), 13, date(2028, 2, 29)),
    ],
)
def test_add_months_clamps_to_the_last_day_of_the_month(
    start: date, months: int, expected: date
) -> None:
    """Month arithmetic never overflows into the next month."""
    assert add_months(start, months) == expected


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 3, 1), 12, date(2027, 2, 28)),
        (date(2026, 10, 1), 12, date(2027, 9, 30)),
        (date(2027, 3, 1), 12, date(2028, 2, 29)),
    ],
)
def test_term_end_is_inclusive(start: date, months: int, expected: date) -> None:
    """A 12-month term starting 2026-03-01 expires 2027-02-28 (E5-S2 AC-1)."""
    assert term_end(start, months) == expected
