"""Cancellation with a pre-computed, append-only refund (AC-08, AC-19, NFR-01, NFR-02, NFR-04).

:meth:`CancellationService.preview` computes the refund breakdown and persists nothing;
:meth:`CancellationService.cancel` appends one immutable ``Refund``, moves the policy to
``CANCELLED`` with its transition row and (for an ADMIN actor) audits ``POLICY_CANCELLED``, in one
transaction. The refund is computed on the rule version recorded on the policy; free look applies to
new business only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from sqlalchemy.orm import Session

from src.config.rule_loader import build_rule_set
from src.domain.policy_state_machine import assert_transition
from src.domain.refund_rules import refund_breakdown
from src.domain.term_days import days_elapsed, term_days
from src.repository.models import AuditAction, AuditEntityType, Policy
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.service.audit_service import AuditService
from src.service.ownership import owned_policy
from src.service.policy_query_service import RefundView
from src.service.quote_service import ActingActor
from src.service.renewal_service import assert_live
from src.types.enums import ActorRole, PolicyStatus, ProductCode, RefundType, RuleSetStatus
from src.types.errors import NoPublishedVersionError, ValidationError
from src.types.rules import RuleSet

CANCELLED_REASON: Final = "CANCELLED"
MAX_REASON_LENGTH: Final = 200


@dataclass(frozen=True, slots=True)
class RefundBreakdownView:
    """Refund preview (contract `RefundBreakdown`): gross pro-rata, fee and net amount."""

    policy_number: str
    cancellation_date: date
    refund_type: RefundType
    premium_paid: Decimal
    term_days: int
    days_elapsed: int
    unused_days: int
    gross_refund: Decimal
    admin_fee: Decimal
    amount: Decimal
    rule_version: int


@dataclass(frozen=True, slots=True)
class CancellationResult:
    """Outcome of a cancellation: the new status and the appended refund."""

    policy_number: str
    status: str
    refund: RefundView


def _validate_reason(reason: str) -> str:
    """The trimmed free-text reason, or 422 when blank or longer than 200 characters."""
    trimmed = reason.strip()
    if not trimmed or len(trimmed) > MAX_REASON_LENGTH:
        raise ValidationError(
            "reason must be 1 to 200 characters", [{"field": "reason", "code": "OUT_OF_RANGE"}]
        )
    return trimmed


class CancellationService:
    """Previews and performs policy cancellations."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._policies = PolicyRepository(session)
        self._lifecycle = PolicyLifecycleRepository(session)
        self._versions = RuleSetVersionRepository(session)
        self._audit = AuditService(session)

    def preview(
        self, policy_number: str, cancellation_date: date, actor: ActingActor
    ) -> RefundBreakdownView:
        """The refund that cancelling on ``cancellation_date`` would pay; persists nothing."""
        policy = owned_policy(self._policies, policy_number, actor)
        assert_live(policy, PolicyStatus.CANCELLED)
        return self._breakdown(policy, cancellation_date)

    def cancel(
        self, policy_number: str, cancellation_date: date, reason: str, actor: ActingActor
    ) -> CancellationResult:
        """Append the refund, move the policy to CANCELLED and audit, in one transaction."""
        try:
            result = self._cancel(policy_number, cancellation_date, reason, actor)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return result

    def _cancel(
        self, policy_number: str, cancellation_date: date, reason: str, actor: ActingActor
    ) -> CancellationResult:
        policy = owned_policy(self._policies, policy_number, actor)
        current = assert_live(policy, PolicyStatus.CANCELLED)
        breakdown = self._breakdown(policy, cancellation_date)
        text = _validate_reason(reason)
        refund = self._lifecycle.add_refund(
            policy_id=policy.id,
            refund_type=breakdown.refund_type,
            premium_paid=breakdown.premium_paid,
            term_days=breakdown.term_days,
            days_elapsed=breakdown.days_elapsed,
            unused_days=breakdown.unused_days,
            admin_fee=breakdown.admin_fee,
            amount=breakdown.amount,
            rule_version=breakdown.rule_version,
            cancellation_date=cancellation_date,
            reason=text,
            actor_id=actor.actor_id,
        )
        assert_transition(current, PolicyStatus.CANCELLED)
        self._policies.update_projection(policy, status=PolicyStatus.CANCELLED)
        self._lifecycle.add_transition(
            policy_id=policy.id,
            from_status=current,
            to_status=PolicyStatus.CANCELLED,
            reason=CANCELLED_REASON,
            actor_id=actor.actor_id,
        )
        if actor.role is ActorRole.ADMIN:
            self._audit.record(
                action=AuditAction.POLICY_CANCELLED,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type=AuditEntityType.POLICY,
                entity_id=policy.policy_number,
                detail={
                    "cancellation_date": cancellation_date.isoformat(),
                    "refund_type": breakdown.refund_type.value,
                    "refund_amount": str(breakdown.amount),
                },
            )
        return CancellationResult(
            policy_number=policy.policy_number,
            status=PolicyStatus.CANCELLED.value,
            refund=RefundView(
                id=refund.id,
                refund_type=refund.refund_type,
                premium_paid=refund.premium_paid,
                term_days=refund.term_days,
                days_elapsed=refund.days_elapsed,
                unused_days=refund.unused_days,
                admin_fee=refund.admin_fee,
                amount=refund.amount,
                rule_version=refund.rule_version,
                cancellation_date=refund.cancellation_date,
                reason=refund.reason,
                actor_id=refund.actor_id,
                created_at=refund.created_at,
            ),
        )

    def _breakdown(self, policy: Policy, cancellation_date: date) -> RefundBreakdownView:
        """Refund maths on the policy's recorded rule version (422 ``OUTSIDE_TERM`` if outside)."""
        rule_set = self._recorded_rule_set(policy)
        premium = self._premium_paid(policy)
        parts = refund_breakdown(
            rule_set,
            premium,
            policy.effective_date,
            policy.expiry_date,
            cancellation_date,
            new_business=policy.previous_policy_number is None,
        )
        total = term_days(policy.effective_date, policy.expiry_date)
        elapsed = days_elapsed(policy.effective_date, cancellation_date)
        return RefundBreakdownView(
            policy_number=policy.policy_number,
            cancellation_date=cancellation_date,
            refund_type=parts.refund_type,
            premium_paid=premium,
            term_days=total,
            days_elapsed=elapsed,
            unused_days=total - elapsed,
            gross_refund=parts.gross,
            admin_fee=parts.admin_fee,
            amount=parts.amount,
            rule_version=policy.rule_version,
        )

    def _premium_paid(self, policy: Policy) -> Decimal:
        """The payment covering this term: issuance payment, or the renewal payment (A-RC-8)."""
        payer = policy
        if policy.previous_policy_number is not None:
            payer = self._policies.get_by_number(policy.previous_policy_number) or policy
        for payment in self._lifecycle.payments_of(payer.id):
            if payment.due_date == policy.effective_date:
                return payment.amount
        return policy.premium

    def _recorded_rule_set(self, policy: Policy) -> RuleSet:
        """Latest PUBLISHED revision of the rule version recorded on the policy."""
        product = ProductCode(policy.product)
        rows = [
            row
            for row in self._versions.list_for_product(product)
            if row.version == policy.rule_version and row.status == RuleSetStatus.PUBLISHED.value
        ]
        if not rows:
            raise NoPublishedVersionError(
                f"Recorded rule version {policy.rule_version} is unavailable"
            )
        row = max(rows, key=lambda candidate: candidate.revision)
        return build_rule_set(row.content, label=f"{product.value} v{row.version}")
