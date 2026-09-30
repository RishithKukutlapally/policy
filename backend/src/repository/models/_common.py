"""Column defaults and CHECK-constraint helpers shared by the model modules.

Money columns are ``Numeric(12, 2)`` and rates ``Numeric(9, 6)`` mapped to :class:`~decimal.Decimal`
— never ``Float`` (NFR-01). Append-only tables are documented as such and their repositories
expose ``add(...)`` plus reads only (NFR-02).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from src.lib.clock import now_utc


def _in_clause(column: str, values: type[StrEnum]) -> str:
    """Render ``column IN ('A', 'B')`` for a CHECK constraint from an enum."""
    rendered = ", ".join(f"'{member.value}'" for member in values)
    return f"{column} IN ({rendered})"


def _new_uuid() -> str:
    """Fresh UUID4 string primary key."""
    return str(uuid.uuid4())


def _now() -> datetime:
    """Current UTC instant, read through the clock module (DEC-012)."""
    return now_utc()
