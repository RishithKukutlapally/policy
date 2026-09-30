"""Append-only repositories for the policy lifecycle tables (NFR-02, AC-05, AC-15).

``policy_state_transitions``, ``endorsements``, ``premium_payments`` and ``refunds`` are written
once: each repository exposes ``add`` plus read methods only — no update, no delete, no merge.
:class:`PolicyLifecycleRepository` bundles the four for services that write a whole lifecycle step
in one transaction. The calling service owns the transaction; nothing here commits.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from src.repository.models import Endorsement, PolicyStateTransition, PremiumPayment, Refund
from src.types.enums import EndorsementType, PolicyStatus, RefundType


def _oldest_first(statement: Select[Any], column: Any) -> Select[Any]:
    """Order by ``column`` with insertion order as the tiebreaker (clock resolution ties)."""
    return statement.order_by(column.asc(), text("rowid"))


class PolicyStateTransitionRepository:
    """Appends and reads ``policy_state_transitions`` rows (E5-S2 AC-5)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        policy_id: str,
        from_status: PolicyStatus | None,
        to_status: PolicyStatus,
        reason: str,
        actor_id: str,
    ) -> PolicyStateTransition:
        """Append one transition row and flush it."""
        row = PolicyStateTransition(
            policy_id=policy_id,
            from_status=None if from_status is None else from_status.value,
            to_status=to_status.value,
            reason=reason,
            actor_id=actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_for_policy(self, policy_id: str) -> list[PolicyStateTransition]:
        """Every transition of one policy, oldest first."""
        statement = _oldest_first(
            select(PolicyStateTransition).where(PolicyStateTransition.policy_id == policy_id),
            PolicyStateTransition.occurred_at,
        )
        return list(self._session.execute(statement).scalars())


class EndorsementRepository:
    """Appends and reads ``endorsements`` rows (AC-06, AC-15)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        policy_id: str,
        endorsement_type: EndorsementType,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        premium_delta: Decimal,
        rule_version: int,
        endorsement_date: date,
        actor_id: str,
    ) -> Endorsement:
        """Append one endorsement row and flush it."""
        row = Endorsement(
            policy_id=policy_id,
            type=endorsement_type.value,
            before=dict(before),
            after=dict(after),
            premium_delta=premium_delta,
            rule_version=rule_version,
            endorsement_date=endorsement_date,
            actor_id=actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_for_policy(self, policy_id: str) -> list[Endorsement]:
        """Every endorsement of one policy, oldest first."""
        statement = _oldest_first(
            select(Endorsement).where(Endorsement.policy_id == policy_id), Endorsement.created_at
        )
        return list(self._session.execute(statement).scalars())


class PremiumPaymentRepository:
    """Appends and reads ``premium_payments`` rows (AC-05, AC-07)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        policy_id: str,
        due_date: date,
        amount: Decimal,
        rule_version: int,
        actor_id: str,
    ) -> PremiumPayment:
        """Append one premium payment and flush it."""
        row = PremiumPayment(
            policy_id=policy_id,
            due_date=due_date,
            amount=amount,
            rule_version=rule_version,
            actor_id=actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_for_policy(self, policy_id: str) -> list[PremiumPayment]:
        """Every payment of one policy, oldest first."""
        statement = _oldest_first(
            select(PremiumPayment).where(PremiumPayment.policy_id == policy_id),
            PremiumPayment.due_date,
        )
        return list(self._session.execute(statement).scalars())


class RefundRepository:
    """Appends and reads the single ``refunds`` row of a cancelled policy (AC-08)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        policy_id: str,
        refund_type: RefundType,
        premium_paid: Decimal,
        term_days: int,
        days_elapsed: int,
        unused_days: int,
        admin_fee: Decimal,
        amount: Decimal,
        rule_version: int,
        cancellation_date: date,
        reason: str,
        actor_id: str,
    ) -> Refund:
        """Append one refund row and flush it."""
        row = Refund(
            policy_id=policy_id,
            refund_type=refund_type.value,
            premium_paid=premium_paid,
            term_days=term_days,
            days_elapsed=days_elapsed,
            unused_days=unused_days,
            admin_fee=admin_fee,
            amount=amount,
            rule_version=rule_version,
            cancellation_date=cancellation_date,
            reason=reason,
            actor_id=actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_for_policy(self, policy_id: str) -> list[Refund]:
        """The refunds of one policy (at most one), oldest first."""
        statement = _oldest_first(
            select(Refund).where(Refund.policy_id == policy_id), Refund.created_at
        )
        return list(self._session.execute(statement).scalars())


class PolicyLifecycleRepository:
    """One append-only facade over the four lifecycle tables (no mutating operation)."""

    def __init__(self, session: Session) -> None:
        self._transitions = PolicyStateTransitionRepository(session)
        self._endorsements = EndorsementRepository(session)
        self._payments = PremiumPaymentRepository(session)
        self._refunds = RefundRepository(session)

    def add_transition(
        self,
        *,
        policy_id: str,
        from_status: PolicyStatus | None,
        to_status: PolicyStatus,
        reason: str,
        actor_id: str,
    ) -> PolicyStateTransition:
        """Append one lifecycle transition."""
        return self._transitions.add(
            policy_id=policy_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor_id=actor_id,
        )

    def add_endorsement(self, **fields: Any) -> Endorsement:
        """Append one endorsement (see :meth:`EndorsementRepository.add`)."""
        return self._endorsements.add(**fields)

    def add_payment(self, **fields: Any) -> PremiumPayment:
        """Append one premium payment (see :meth:`PremiumPaymentRepository.add`)."""
        return self._payments.add(**fields)

    def add_refund(self, **fields: Any) -> Refund:
        """Append one refund (see :meth:`RefundRepository.add`)."""
        return self._refunds.add(**fields)

    def transitions_of(self, policy_id: str) -> list[PolicyStateTransition]:
        """Transitions of one policy, oldest first."""
        return self._transitions.list_for_policy(policy_id)

    def endorsements_of(self, policy_id: str) -> list[Endorsement]:
        """Endorsements of one policy, oldest first."""
        return self._endorsements.list_for_policy(policy_id)

    def payments_of(self, policy_id: str) -> list[PremiumPayment]:
        """Premium payments of one policy, oldest first."""
        return self._payments.list_for_policy(policy_id)

    def refunds_of(self, policy_id: str) -> list[Refund]:
        """Refunds of one policy (at most one)."""
        return self._refunds.list_for_policy(policy_id)
