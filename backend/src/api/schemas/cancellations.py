"""Request / response schemas for cancellation (contracts 2.23 and 2.24, AC-08, AC-19).

Money is a two-decimal string; dates are ISO-8601.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from src.api.schemas.quotes import money, timestamp
from src.service.cancellation_service import CancellationResult, RefundBreakdownView


class CancelRequest(BaseModel):
    """``POST /api/policies/{number}/cancel`` body; ``reason`` is free text, 1 to 200 chars."""

    cancellation_date: date
    reason: str


class RefundBreakdownResponse(BaseModel):
    """``GET /api/policies/{number}/cancellation-preview``."""

    policy_number: str
    cancellation_date: str
    refund_type: str
    premium_paid: str
    term_days: int
    days_elapsed: int
    unused_days: int
    gross_refund: str
    admin_fee: str
    amount: str
    rule_version: int

    @classmethod
    def from_view(cls, view: RefundBreakdownView) -> RefundBreakdownResponse:
        """Build from a refund breakdown view."""
        return cls(
            policy_number=view.policy_number,
            cancellation_date=view.cancellation_date.isoformat(),
            refund_type=view.refund_type.value,
            premium_paid=money(view.premium_paid),
            term_days=view.term_days,
            days_elapsed=view.days_elapsed,
            unused_days=view.unused_days,
            gross_refund=money(view.gross_refund),
            admin_fee=money(view.admin_fee),
            amount=money(view.amount),
            rule_version=view.rule_version,
        )


class RefundResponse(BaseModel):
    """The persisted refund of a cancelled policy."""

    refund_id: str
    policy_number: str
    cancellation_date: str
    refund_type: str
    premium_paid: str
    term_days: int
    days_elapsed: int
    unused_days: int
    admin_fee: str
    amount: str
    rule_version: int
    reason: str
    actor_id: str
    created_at: str


class CancelResponse(BaseModel):
    """``POST /api/policies/{number}/cancel`` result."""

    policy_number: str
    status: str
    refund: RefundResponse

    @classmethod
    def from_result(cls, result: CancellationResult) -> CancelResponse:
        """Build from a cancellation result."""
        refund = result.refund
        return cls(
            policy_number=result.policy_number,
            status=result.status,
            refund=RefundResponse(
                refund_id=refund.id,
                policy_number=result.policy_number,
                cancellation_date=refund.cancellation_date.isoformat(),
                refund_type=refund.refund_type,
                premium_paid=money(refund.premium_paid),
                term_days=refund.term_days,
                days_elapsed=refund.days_elapsed,
                unused_days=refund.unused_days,
                admin_fee=money(refund.admin_fee),
                amount=money(refund.amount),
                rule_version=refund.rule_version,
                reason=refund.reason,
                actor_id=refund.actor_id,
                created_at=timestamp(refund.created_at),
            ),
        )
