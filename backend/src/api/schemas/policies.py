"""Response schemas for the policy endpoints (contracts 2.16 to 2.18, AC-05, AC-15).

Money is serialised as a two-decimal string and dates as ISO-8601 (NFR-01); only masked
identifiers ever leave the API (NFR-03).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.api.schemas.quotes import money, timestamp
from src.service.policy_query_service import (
    EndorsementView,
    InsuredView,
    PaymentView,
    PolicyDetailView,
    RefundView,
    TransitionView,
)
from src.service.policy_service import PolicySummaryView


class PolicySummaryResponse(BaseModel):
    """One policy term as listed by ``GET /api/policies``."""

    policy_number: str
    product: str
    status: str
    rule_version: int
    sum_insured: str
    premium: str
    currency: str
    effective_date: str
    expiry_date: str
    premium_due_date: str
    next_premium_due_date: str
    previous_policy_number: str | None

    @classmethod
    def from_view(cls, view: PolicySummaryView) -> PolicySummaryResponse:
        """Build from a policy summary view."""
        return cls(
            policy_number=view.policy_number,
            product=view.product,
            status=view.status,
            rule_version=view.rule_version,
            sum_insured=money(view.sum_insured),
            premium=money(view.premium),
            currency=view.currency,
            effective_date=view.effective_date.isoformat(),
            expiry_date=view.expiry_date.isoformat(),
            premium_due_date=view.premium_due_date.isoformat(),
            next_premium_due_date=view.next_premium_due_date.isoformat(),
            previous_policy_number=view.previous_policy_number,
        )


class InsuredResponse(BaseModel):
    """Masked applicant details of the policy."""

    full_name: str
    address: str
    aadhaar_masked: str
    pan_masked: str
    nominees: list[dict[str, Any]]

    @classmethod
    def from_view(cls, view: InsuredView) -> InsuredResponse:
        """Build from an insured view."""
        return cls(
            full_name=view.full_name,
            address=view.address,
            aadhaar_masked=view.aadhaar_masked,
            pan_masked=view.pan_masked,
            nominees=[dict(n) for n in view.nominees],
        )


class TransitionResponse(BaseModel):
    """One lifecycle step of the policy."""

    from_status: str | None
    to_status: str
    reason: str
    actor_id: str
    occurred_at: str

    @classmethod
    def from_view(cls, view: TransitionView) -> TransitionResponse:
        """Build from a transition view."""
        return cls(
            from_status=view.from_status,
            to_status=view.to_status,
            reason=view.reason,
            actor_id=view.actor_id,
            occurred_at=timestamp(view.occurred_at),
        )


class EndorsementResponse(BaseModel):
    """One endorsement of the policy history."""

    endorsement_id: str
    type: str
    before: dict[str, Any]
    after: dict[str, Any]
    premium_delta: str
    rule_version: int
    endorsement_date: str
    actor_id: str
    created_at: str

    @classmethod
    def from_view(cls, view: EndorsementView) -> EndorsementResponse:
        """Build from an endorsement view."""
        return cls(
            endorsement_id=view.id,
            type=view.type,
            before=dict(view.before),
            after=dict(view.after),
            premium_delta=money(view.premium_delta),
            rule_version=view.rule_version,
            endorsement_date=view.endorsement_date.isoformat(),
            actor_id=view.actor_id,
            created_at=timestamp(view.created_at),
        )


class PaymentResponse(BaseModel):
    """One premium payment."""

    payment_id: str
    due_date: str
    amount: str
    rule_version: int
    actor_id: str
    paid_at: str

    @classmethod
    def from_view(cls, view: PaymentView) -> PaymentResponse:
        """Build from a payment view."""
        return cls(
            payment_id=view.id,
            due_date=view.due_date.isoformat(),
            amount=money(view.amount),
            rule_version=view.rule_version,
            actor_id=view.actor_id,
            paid_at=timestamp(view.paid_at),
        )


class RefundResponse(BaseModel):
    """The refund of a cancelled policy."""

    refund_id: str
    refund_type: str
    premium_paid: str
    term_days: int
    days_elapsed: int
    unused_days: int
    admin_fee: str
    amount: str
    rule_version: int
    cancellation_date: str
    reason: str
    actor_id: str
    created_at: str

    @classmethod
    def from_view(cls, view: RefundView) -> RefundResponse:
        """Build from a refund view."""
        return cls(
            refund_id=view.id,
            refund_type=view.refund_type,
            premium_paid=money(view.premium_paid),
            term_days=view.term_days,
            days_elapsed=view.days_elapsed,
            unused_days=view.unused_days,
            admin_fee=money(view.admin_fee),
            amount=money(view.amount),
            rule_version=view.rule_version,
            cancellation_date=view.cancellation_date.isoformat(),
            reason=view.reason,
            actor_id=view.actor_id,
            created_at=timestamp(view.created_at),
        )


class PolicyDetailResponse(PolicySummaryResponse):
    """``GET /api/policies/{policy_number}``: the summary plus the full history."""

    application_id: str
    successor_policy_number: str | None
    insured: InsuredResponse
    transitions: list[TransitionResponse]
    endorsements: list[EndorsementResponse]
    payments: list[PaymentResponse]
    refunds: list[RefundResponse]

    @classmethod
    def from_detail(cls, view: PolicyDetailView) -> PolicyDetailResponse:
        """Build from a policy detail view."""
        summary = PolicySummaryResponse.from_view(view.summary)
        return cls(
            **summary.model_dump(),
            application_id=view.application_id,
            successor_policy_number=view.successor_policy_number,
            insured=InsuredResponse.from_view(view.insured),
            transitions=[TransitionResponse.from_view(t) for t in view.transitions],
            endorsements=[EndorsementResponse.from_view(e) for e in view.endorsements],
            payments=[PaymentResponse.from_view(p) for p in view.payments],
            refunds=[RefundResponse.from_view(r) for r in view.refunds],
        )
