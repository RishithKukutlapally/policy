"""Policy read models for My Policies and Policy Detail (AC-15).

CUSTOMER callers are owner-scoped: another customer's policy is reported as
:class:`~src.types.errors.NotFoundError` (404, no existence leak). Every method returns view
dataclasses so the API layer never touches an ORM row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.repository.application_repository import ApplicationRepository
from src.repository.models import Endorsement, PolicyStateTransition, PremiumPayment, Refund
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.service.ownership import owned_policy
from src.service.policy_service import PolicySummaryView, summary_view
from src.service.quote_service import ActingActor
from src.types.enums import ActorRole, PolicyStatus, ProductCode
from src.types.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class InsuredView:
    """Masked applicant details shown on Policy Detail (NFR-03)."""

    full_name: str
    address: str
    aadhaar_masked: str
    pan_masked: str
    nominees: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class TransitionView:
    """One lifecycle step."""

    from_status: str | None
    to_status: str
    reason: str
    actor_id: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class EndorsementView:
    """One endorsement of the policy's history."""

    id: str
    type: str
    before: dict[str, Any]
    after: dict[str, Any]
    premium_delta: Decimal
    rule_version: int
    endorsement_date: date
    actor_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PaymentView:
    """One premium payment."""

    id: str
    due_date: date
    amount: Decimal
    rule_version: int
    actor_id: str
    paid_at: datetime


@dataclass(frozen=True, slots=True)
class RefundView:
    """The refund of a cancelled policy."""

    id: str
    refund_type: str
    premium_paid: Decimal
    term_days: int
    days_elapsed: int
    unused_days: int
    admin_fee: Decimal
    amount: Decimal
    rule_version: int
    cancellation_date: date
    reason: str
    actor_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PolicyDetailView:
    """Policy Detail: the summary plus insured details and the full lifecycle history."""

    summary: PolicySummaryView
    application_id: str
    successor_policy_number: str | None
    insured: InsuredView
    transitions: tuple[TransitionView, ...]
    endorsements: tuple[EndorsementView, ...]
    payments: tuple[PaymentView, ...]
    refunds: tuple[RefundView, ...]


def _transition_view(row: PolicyStateTransition) -> TransitionView:
    return TransitionView(
        from_status=row.from_status,
        to_status=row.to_status,
        reason=row.reason,
        actor_id=row.actor_id,
        occurred_at=row.occurred_at,
    )


def _endorsement_view(row: Endorsement) -> EndorsementView:
    return EndorsementView(
        id=row.id,
        type=row.type,
        before=dict(row.before),
        after=dict(row.after),
        premium_delta=row.premium_delta,
        rule_version=row.rule_version,
        endorsement_date=row.endorsement_date,
        actor_id=row.actor_id,
        created_at=row.created_at,
    )


def _payment_view(row: PremiumPayment) -> PaymentView:
    return PaymentView(
        id=row.id,
        due_date=row.due_date,
        amount=row.amount,
        rule_version=row.rule_version,
        actor_id=row.actor_id,
        paid_at=row.paid_at,
    )


def _refund_view(row: Refund) -> RefundView:
    return RefundView(
        id=row.id,
        refund_type=row.refund_type,
        premium_paid=row.premium_paid,
        term_days=row.term_days,
        days_elapsed=row.days_elapsed,
        unused_days=row.unused_days,
        admin_fee=row.admin_fee,
        amount=row.amount,
        rule_version=row.rule_version,
        cancellation_date=row.cancellation_date,
        reason=row.reason,
        actor_id=row.actor_id,
        created_at=row.created_at,
    )


class PolicyQueryService:
    """Owner-scoped policy reads for the list and detail screens (AC-15)."""

    def __init__(self, session: Session) -> None:
        self._policies = PolicyRepository(session)
        self._lifecycle = PolicyLifecycleRepository(session)
        self._applications = ApplicationRepository(session)

    def list_policies(
        self,
        actor: ActingActor,
        *,
        product: ProductCode | None = None,
        status: PolicyStatus | None = None,
    ) -> tuple[PolicySummaryView, ...]:
        """Policies visible to ``actor``: own only for a CUSTOMER, all for staff."""
        if actor.role is ActorRole.CUSTOMER:
            rows = self._policies.list_for_customer(actor.actor_id, product=product, status=status)
        else:
            rows = self._policies.list_all(product=product, status=status)
        return tuple(summary_view(row) for row in rows)

    def get_policy(self, policy_number: str, actor: ActingActor) -> PolicyDetailView:
        """Policy Detail, or 404 when the number is unknown or owned by someone else."""
        row = owned_policy(self._policies, policy_number, actor)
        application = self._applications.get(row.application_id)
        if application is None:  # pragma: no cover - guarded by the policies FK
            raise NotFoundError("Policy not found")
        successor = self._policies.successor_of(row.policy_number)
        return PolicyDetailView(
            summary=summary_view(row),
            application_id=row.application_id,
            successor_policy_number=None if successor is None else successor.policy_number,
            insured=InsuredView(
                full_name=application.full_name,
                address=row.address,
                aadhaar_masked=application.aadhaar_masked,
                pan_masked=application.pan_masked,
                nominees=tuple(dict(n) for n in row.nominees),
            ),
            transitions=tuple(_transition_view(t) for t in self._lifecycle.transitions_of(row.id)),
            endorsements=tuple(
                _endorsement_view(e) for e in self._lifecycle.endorsements_of(row.id)
            ),
            payments=tuple(_payment_view(p) for p in self._lifecycle.payments_of(row.id)),
            refunds=tuple(_refund_view(r) for r in self._lifecycle.refunds_of(row.id)),
        )
