"""Pure day maths for premium, endorsement and refund rules. Dates are always passed in."""

from datetime import date

from src.types.errors import ValidationError


def term_days(effective_date: date, expiry_date: date) -> int:
    """Inclusive term length: `(expiry - effective).days + 1`."""
    if expiry_date < effective_date:
        raise ValidationError("expiry_date precedes effective_date")
    return (expiry_date - effective_date).days + 1


def days_elapsed(effective_date: date, on: date) -> int:
    """Whole days from `effective_date` to `on`."""
    return (on - effective_date).days


def unused_days(effective_date: date, expiry_date: date, on: date) -> int:
    """Term days not yet consumed at `on`, clamped to `0..term_days`."""
    total = term_days(effective_date, expiry_date)
    return max(0, min(total, total - days_elapsed(effective_date, on)))
