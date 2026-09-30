"""Insert-only repository for ``quotes`` (AC-13).

Public surface: ``add`` and ``get``. There is no update and no delete. The session belongs to
the calling service, which owns the transaction; this repository never commits.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.repository.models import Quote


class QuoteRepository:
    """Stages new quote rows and reads them back."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        product: str,
        rule_version: int,
        inputs: Mapping[str, Any],
        sum_insured: Decimal,
        premium: Decimal,
        breakdown: Mapping[str, Any],
        actor_id: str,
    ) -> Quote:
        """Insert one quote and flush it."""
        row = Quote(
            product=product,
            rule_version=rule_version,
            inputs=dict(inputs),
            sum_insured=sum_insured,
            premium=premium,
            breakdown=dict(breakdown),
            actor_id=actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, quote_id: str) -> Quote | None:
        """The quote with ``quote_id``, or ``None``."""
        return self._session.get(Quote, quote_id)
