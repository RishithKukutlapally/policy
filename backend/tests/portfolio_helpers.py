"""Deterministic portfolio seeding helpers for the E9-S1 tests (synthetic data only).

Rows are written straight through the repositories so each figure the dashboard reports can be
computed by hand with :mod:`decimal`. ``paid_at`` / ``created_at`` default to the business date
(DEC-012), so the helpers set ``POLICYFORGE_BUSINESS_DATE`` while a row is staged to control the
date on which money is treated as collected.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.repository.application_repository import ApplicationRepository
from src.repository.models import Policy
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.repository.quote_repository import QuoteRepository
from src.types.enums import (
    ActorRole,
    ApplicationStatus,
    PolicyStatus,
    ProductCode,
    RefundType,
)

BUSINESS_DATE_ENV = "POLICYFORGE_BUSINESS_DATE"

#: Business date every portfolio test reports on.
AS_OF = date(2027, 1, 1)

#: Date on which the seeded money is treated as collected (before :data:`AS_OF`).
COLLECTED_ON = date(2026, 12, 31)


@dataclass(frozen=True, slots=True)
class FakeActor:
    """Structural stand-in for the API layer's ``Actor`` (services never import `src.api`)."""

    actor_id: str = "admin-001"
    role: ActorRole = ActorRole.ADMIN

    @property
    def id(self) -> str:
        """Alias used by call sites that read ``actor.id``."""
        return self.actor_id


@contextmanager
def at_business_date(value: date) -> Iterator[None]:
    """Run the block with the business date pinned to ``value`` (restored afterwards)."""
    previous = os.environ.get(BUSINESS_DATE_ENV)
    os.environ[BUSINESS_DATE_ENV] = value.isoformat()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(BUSINESS_DATE_ENV, None)
        else:
            os.environ[BUSINESS_DATE_ENV] = previous


def _application_id(session: Session, product: ProductCode, customer_id: str) -> str:
    """Stage the quote and application a policy row needs as its foreign keys."""
    quote = QuoteRepository(session).add(
        product=product.value,
        rule_version=1,
        inputs={"sum_insured": "100000.00"},
        sum_insured=Decimal("100000.00"),
        premium=Decimal("1000.00"),
        breakdown={},
        actor_id=customer_id,
    )
    application = ApplicationRepository(session).add(
        quote_id=quote.id,
        customer_id=customer_id,
        product=product.value,
        rule_version=1,
        status=ApplicationStatus.ISSUED,
        status_history=[ApplicationStatus.SUBMITTED.value, ApplicationStatus.ISSUED.value],
        full_name="Test Customer 01",
        date_of_birth=date(1990, 1, 1),
        address="1 Sample Street, Testville",
        aadhaar_masked="XXXX-XXXX-0001",
        pan_masked="XXXXX0001X",
        risk_inputs={"sum_insured": "100000.00"},
    )
    return application.id


def seed_policy(
    session: Session,
    *,
    policy_number: str,
    product: ProductCode,
    status: PolicyStatus,
    sum_insured: Decimal,
    premium: Decimal,
    effective_date: date,
    expiry_date: date,
    customer_id: str = "cust-001",
    rule_version: int = 1,
) -> Policy:
    """Stage one policy row (with its quote/application parents) and return it."""
    return PolicyRepository(session).add(
        policy_number=policy_number,
        product=product.value,
        application_id=_application_id(session, product, customer_id),
        customer_id=customer_id,
        rule_version=rule_version,
        rating_inputs={"sum_insured": str(sum_insured)},
        sum_insured=sum_insured,
        premium=premium,
        effective_date=effective_date,
        expiry_date=expiry_date,
        premium_due_date=effective_date,
        status=status,
        address="1 Sample Street, Testville",
    )


def seed_payment(
    session: Session,
    policy: Policy,
    *,
    due_date: date,
    amount: Decimal,
    collected_on: date = COLLECTED_ON,
) -> None:
    """Append one premium payment collected on ``collected_on``."""
    with at_business_date(collected_on):
        PolicyLifecycleRepository(session).add_payment(
            policy_id=policy.id,
            due_date=due_date,
            amount=amount,
            rule_version=1,
            actor_id=policy.customer_id,
        )


def seed_refund(
    session: Session,
    policy: Policy,
    *,
    premium_paid: Decimal,
    amount: Decimal,
    term_days: int,
    days_elapsed: int,
    admin_fee: Decimal,
    cancellation_date: date,
    collected_on: date = COLLECTED_ON,
) -> None:
    """Append the single refund row of a cancelled policy, paid out on ``collected_on``."""
    with at_business_date(collected_on):
        PolicyLifecycleRepository(session).add_refund(
            policy_id=policy.id,
            refund_type=RefundType.PRO_RATA,
            premium_paid=premium_paid,
            term_days=term_days,
            days_elapsed=days_elapsed,
            unused_days=term_days - days_elapsed,
            admin_fee=admin_fee,
            amount=amount,
            rule_version=1,
            cancellation_date=cancellation_date,
            reason="Vehicle sold",
            actor_id="admin-001",
        )
