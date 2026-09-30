"""Simulated renewal-premium payments (AC-17, NFR-01, NFR-02).

There is no gateway: :meth:`PaymentService.record_payment` appends one immutable ``PremiumPayment``
for the renewal due on ``expiry_date + 1 day``. The amount must equal the current renewal quote;
a paid policy is renewed, never lapsed, by the end-of-day job.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.domain.money import has_at_most_two_decimals
from src.lib.clock import today
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.service.ownership import owned_policy
from src.service.quote_service import ActingActor
from src.service.renewal_service import RenewalService, assert_live
from src.types.enums import PolicyStatus
from src.types.errors import PremiumAlreadyPaidError, ValidationError


@dataclass(frozen=True, slots=True)
class PaymentRecord:
    """Read model of one recorded payment (contract 2.22)."""

    id: str
    policy_number: str
    amount: Decimal
    due_date: date
    rule_version: int
    actor_id: str
    paid_at: datetime


def _validate_amount(amount: Decimal) -> None:
    """422 unless ``amount`` is a positive money value with at most two decimals."""
    if not has_at_most_two_decimals(amount):
        raise ValidationError(
            "amount must have at most 2 decimals", [{"field": "amount", "code": "INVALID_FORMAT"}]
        )
    if amount <= 0:
        raise ValidationError(
            "amount must be positive", [{"field": "amount", "code": "OUT_OF_RANGE"}]
        )


class PaymentService:
    """Records renewal-premium payments for the owning customer."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._policies = PolicyRepository(session)
        self._lifecycle = PolicyLifecycleRepository(session)
        self._renewals = RenewalService(session)

    def record_payment(
        self, policy_number: str, amount: Decimal, actor: ActingActor
    ) -> PaymentRecord:
        """Append the payment of the renewal due next; nothing is stored on any refusal."""
        try:
            record = self._record(policy_number, amount, actor)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return record

    def _record(self, policy_number: str, amount: Decimal, actor: ActingActor) -> PaymentRecord:
        policy = owned_policy(self._policies, policy_number, actor)
        assert_live(policy, PolicyStatus.RENEWED)
        _validate_amount(amount)
        context = self._renewals.build_context(policy)
        self._renewals.assert_window_open(policy, context, today())
        if not context.renewable or context.premium is None:
            raise ValidationError(
                "Policy is not renewable", [{"field": "policy_number", "code": "NOT_RENEWABLE"}]
            )
        due_date = context.schedule.due_date
        if self._renewals.payment_for(policy, due_date) is not None:
            raise PremiumAlreadyPaidError(
                "The renewal premium is already paid", {"due_date": due_date.isoformat()}
            )
        if amount != context.premium:
            raise ValidationError(
                "amount differs from the renewal premium due",
                [{"field": "amount", "code": "AMOUNT_MISMATCH"}],
            )
        row = self._lifecycle.add_payment(
            policy_id=policy.id,
            due_date=due_date,
            amount=amount,
            rule_version=context.rule_version,
            actor_id=actor.actor_id,
        )
        return PaymentRecord(
            id=row.id,
            policy_number=policy.policy_number,
            amount=row.amount,
            due_date=row.due_date,
            rule_version=row.rule_version,
            actor_id=row.actor_id,
            paid_at=row.paid_at,
        )
