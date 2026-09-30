"""Repository for the ``policies`` current projection (AC-05, AC-10, AC-15).

``policies`` is a projection: :meth:`PolicyRepository.update_projection` moves ``status`` and the
endorsable attributes forward, while the history lives in the append-only lifecycle tables. There
is no delete. The calling service owns the transaction; this repository never commits.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.lib.clock import now_utc
from src.repository.models import Policy
from src.types.enums import PolicyStatus, ProductCode


class PolicyRepository:
    """Stages new policies, moves the projection and reads policies back."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        policy_number: str,
        product: str,
        application_id: str,
        customer_id: str,
        rule_version: int,
        rating_inputs: Mapping[str, Any],
        sum_insured: Decimal,
        premium: Decimal,
        effective_date: date,
        expiry_date: date,
        premium_due_date: date,
        status: PolicyStatus,
        address: str,
        nominees: Sequence[Mapping[str, Any]] = (),
        previous_policy_number: str | None = None,
    ) -> Policy:
        """Insert one policy row and flush it so its defaults are populated."""
        row = Policy(
            policy_number=policy_number,
            product=product,
            application_id=application_id,
            customer_id=customer_id,
            rule_version=rule_version,
            rating_inputs=dict(rating_inputs),
            sum_insured=sum_insured,
            premium=premium,
            effective_date=effective_date,
            expiry_date=expiry_date,
            premium_due_date=premium_due_date,
            status=status.value,
            address=address,
            nominees=[dict(n) for n in nominees],
            previous_policy_number=previous_policy_number,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_by_number(self, policy_number: str) -> Policy | None:
        """The policy with ``policy_number``, or ``None``."""
        statement = select(Policy).where(Policy.policy_number == policy_number)
        return self._session.execute(statement).scalars().one_or_none()

    def list_for_customer(
        self,
        customer_id: str,
        *,
        product: ProductCode | None = None,
        status: PolicyStatus | None = None,
    ) -> list[Policy]:
        """Policies owned by ``customer_id``, ordered by effective date then number."""
        return self._list(customer_id=customer_id, product=product, status=status)

    def list_all(
        self, *, product: ProductCode | None = None, status: PolicyStatus | None = None
    ) -> list[Policy]:
        """Every policy, ordered by effective date then number (staff view)."""
        return self._list(customer_id=None, product=product, status=status)

    def next_sequence(self, prefix: str, year: int) -> int:
        """The next per-prefix/per-year sequence number (1 when none exists yet)."""
        like = f"{prefix}-{year:04d}-%"
        statement = select(Policy.policy_number).where(Policy.policy_number.like(like))
        numbers = [
            int(value.rsplit("-", 1)[1]) for value in self._session.execute(statement).scalars()
        ]
        return max(numbers, default=0) + 1

    def successor_of(self, policy_number: str) -> Policy | None:
        """The renewal successor of ``policy_number``, when one exists."""
        statement = select(Policy).where(Policy.previous_policy_number == policy_number)
        return self._session.execute(statement).scalars().one_or_none()

    def update_projection(
        self,
        policy: Policy,
        *,
        status: PolicyStatus | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> Policy:
        """Move the projection: optional new ``status`` and/or endorsable ``attributes``."""
        if status is not None:
            policy.status = status.value
        for name, value in (attributes or {}).items():
            if not hasattr(policy, name):
                raise AttributeError(f"policies has no attribute {name!r}")
            setattr(policy, name, value)
        policy.updated_at = now_utc()
        self._session.flush()
        return policy

    def _list(
        self,
        *,
        customer_id: str | None,
        product: ProductCode | None,
        status: PolicyStatus | None,
    ) -> list[Policy]:
        statement = select(Policy)
        if customer_id is not None:
            statement = statement.where(Policy.customer_id == customer_id)
        if product is not None:
            statement = statement.where(Policy.product == product.value)
        if status is not None:
            statement = statement.where(Policy.status == status.value)
        statement = statement.order_by(Policy.effective_date.asc(), Policy.policy_number.asc())
        return list(self._session.execute(statement).scalars())
