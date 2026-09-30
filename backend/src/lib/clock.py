"""Business-date provider (DEC-012).

``src/lib`` may import the standard library only (docs/conventions.md -> "Layer import
rules"), so this module reads ``POLICYFORGE_BUSINESS_DATE`` (or the bare ``BUSINESS_DATE``)
from the environment directly instead of importing :mod:`src.config.settings` — the same
variable ``Settings.business_date`` reads. Every layer must ask for "today" here; calling
:func:`datetime.date.today` elsewhere is an architecture violation.
"""

from __future__ import annotations

import datetime as dt
import os

BUSINESS_DATE_ENV_VARS = ("POLICYFORGE_BUSINESS_DATE", "BUSINESS_DATE")


def _configured_business_date() -> dt.date | None:
    """Return the configured business date, or ``None`` when no override is set."""
    for name in BUSINESS_DATE_ENV_VARS:
        raw = os.environ.get(name)
        if raw is None or not raw.strip():
            continue
        try:
            return dt.date.fromisoformat(raw.strip())
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD), got {raw!r}") from exc
    return None


def today() -> dt.date:
    """Return the current business date: the configured override, else the real today."""
    return _configured_business_date() or dt.date.today()


def now_utc() -> dt.datetime:
    """Return the current UTC timestamp (business date applied when overridden)."""
    override = _configured_business_date()
    now = dt.datetime.now(dt.UTC)
    if override is None:
        return now
    return dt.datetime.combine(override, now.timetz())
