"""Request and response schemas for the quote endpoints (contract 2.7 - 2.9).

Money is serialised as a two-decimal string (NFR-01); inputs stay a free mapping because the
per-product field rules live in the rule file and the service validator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.service.quote_service import QuoteView, RepriceResult

_CENT = Decimal("0.01")


def money(value: Decimal) -> str:
    """Two-decimal money string."""
    return str(value.quantize(_CENT, ROUND_HALF_UP))


def timestamp(value: datetime) -> str:
    """ISO 8601 UTC timestamp with a ``Z`` suffix."""
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class QuoteRequest(BaseModel):
    """``POST /api/quotes`` body."""

    model_config = ConfigDict(extra="forbid")

    product: str
    inputs: dict[str, Any]


class QuoteResponse(BaseModel):
    """Created-quote response."""

    quote_id: str
    product: str
    rule_version: int
    sum_insured: str
    premium: str
    currency: str
    created_at: str

    @classmethod
    def from_quote(cls, quote: QuoteView) -> QuoteResponse:
        """Build from a stored quote."""
        return cls(
            quote_id=quote.id,
            product=quote.product,
            rule_version=quote.rule_version,
            sum_insured=money(quote.sum_insured),
            premium=money(quote.premium),
            currency=quote.currency,
            created_at=timestamp(quote.created_at),
        )


class QuoteDetailResponse(QuoteResponse):
    """``GET /api/quotes/{id}`` response: the summary plus inputs and owner."""

    inputs: dict[str, Any]
    actor_id: str

    @classmethod
    def from_quote(cls, quote: QuoteView) -> QuoteDetailResponse:
        """Build from a stored quote."""
        summary = QuoteResponse.from_quote(quote)
        return cls(**summary.model_dump(), inputs=quote.inputs, actor_id=quote.actor_id)


class RepriceResponse(BaseModel):
    """``GET /api/quotes/{id}/reprice`` response."""

    quote_id: str
    rule_version: int
    stored_premium: str
    recomputed_premium: str
    matches: bool

    @classmethod
    def from_result(cls, result: RepriceResult) -> RepriceResponse:
        """Build from a reprice result."""
        return cls(
            quote_id=result.quote_id,
            rule_version=result.rule_version,
            stored_premium=money(result.stored_premium),
            recomputed_premium=money(result.recomputed_premium),
            matches=result.matches,
        )
