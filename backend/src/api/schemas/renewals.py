"""Request / response schemas for renewal, payment and end-of-day (contracts 2.20 to 2.22, 2.25).

Money is a two-decimal string on the way out and a string (never a JSON number) on the way in.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from src.api.schemas.quotes import money, timestamp
from src.jobs.end_of_day import EndOfDayResult
from src.service.payment_service import PaymentRecord
from src.service.renewal_service import RenewalQuoteView
from src.types.errors import ValidationError


class RenewalQuoteResponse(BaseModel):
    """``GET /api/policies/{number}/renewal``."""

    policy_number: str
    renewable: bool
    renewal_premium: str | None
    rule_version: int
    currency: str
    due_date: str
    grace_end_date: str
    renewal_window_opens: str
    paid: bool

    @classmethod
    def from_view(cls, view: RenewalQuoteView) -> RenewalQuoteResponse:
        """Build from a renewal quote view."""
        return cls(
            policy_number=view.policy_number,
            renewable=view.renewable,
            renewal_premium=None if view.renewal_premium is None else money(view.renewal_premium),
            rule_version=view.rule_version,
            currency=view.currency,
            due_date=view.due_date.isoformat(),
            grace_end_date=view.grace_end_date.isoformat(),
            renewal_window_opens=view.renewal_window_opens.isoformat(),
            paid=view.paid,
        )


class PaymentRequest(BaseModel):
    """``POST /api/policies/{number}/payments`` body; ``amount`` must be a money string."""

    amount: object

    def to_decimal(self) -> Decimal:
        """The amount as a ``Decimal``; 422 for a JSON number or an unparsable string."""
        if not isinstance(self.amount, str):
            raise ValidationError(
                "amount must be a string", [{"field": "amount", "code": "MONEY_MUST_BE_STRING"}]
            )
        try:
            return Decimal(self.amount.strip())
        except InvalidOperation:
            raise ValidationError(
                "amount is not a decimal string", [{"field": "amount", "code": "INVALID_FORMAT"}]
            ) from None


class PaymentResponse(BaseModel):
    """A recorded renewal-premium payment."""

    payment_id: str
    policy_number: str
    amount: str
    due_date: str
    rule_version: int
    actor_id: str
    paid_at: str

    @classmethod
    def from_record(cls, record: PaymentRecord) -> PaymentResponse:
        """Build from a payment record."""
        return cls(
            payment_id=record.id,
            policy_number=record.policy_number,
            amount=money(record.amount),
            due_date=record.due_date.isoformat(),
            rule_version=record.rule_version,
            actor_id=record.actor_id,
            paid_at=timestamp(record.paid_at),
        )


class EndOfDayRequest(BaseModel):
    """``POST /api/admin/end-of-day`` body."""

    as_of: date


class FailedPolicyResponse(BaseModel):
    """A policy the run skipped."""

    policy_number: str
    error: str


class EndOfDayResponse(BaseModel):
    """Result of one end-of-day run."""

    as_of: str
    renewed: int
    lapsed: int
    in_grace: int
    not_renewable: int
    failed: int
    renewed_policies: list[dict[str, str]]
    lapsed_policies: list[str]
    failed_policies: list[FailedPolicyResponse]

    @classmethod
    def from_result(cls, result: EndOfDayResult) -> EndOfDayResponse:
        """Build from a run result."""
        return cls(
            as_of=result.as_of.isoformat(),
            renewed=len(result.renewed),
            lapsed=len(result.lapsed),
            in_grace=result.in_grace,
            not_renewable=result.not_renewable,
            failed=len(result.failed),
            renewed_policies=[{"from": old, "to": new} for old, new in result.renewed],
            lapsed_policies=list(result.lapsed),
            failed_policies=[
                FailedPolicyResponse(policy_number=f.policy_number, error=f.error)
                for f in result.failed
            ],
        )
