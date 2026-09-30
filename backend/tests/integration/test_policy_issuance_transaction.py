"""Issuance is one transaction: a failure after the policy insert persists nothing (AC-05)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.repository.models import Application, Policy, PolicyStateTransition, PremiumPayment
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.service.policy_service import PolicyService
from src.types.enums import ActorRole
from tests.policy_helpers import ISSUE_DATE, auto_bind_application

pytestmark = pytest.mark.integration


@pytest.fixture(name="business_date", autouse=True)
def _business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the business date on the golden issuance day (DEC-012)."""
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ISSUE_DATE)


class _Actor:
    """Structural stand-in for the API layer's ``Actor``."""

    def __init__(self, actor_id: str, role: ActorRole) -> None:
        self.actor_id = actor_id
        self.role = role


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def test_failed_transition_leaves_no_policy(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injecting a failure into the transition insert rolls the whole issuance back."""
    application_id = auto_bind_application(api_client)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("transition insert failed")

    monkeypatch.setattr(PolicyLifecycleRepository, "add_transition", _boom)
    with Session(seeded_engine) as session, pytest.raises(RuntimeError):
        PolicyService(session).issue(application_id, _Actor("cust-001", ActorRole.CUSTOMER))
    assert _count(seeded_engine, Policy) == 0
    assert _count(seeded_engine, PolicyStateTransition) == 0
    assert _count(seeded_engine, PremiumPayment) == 0
    with Session(seeded_engine) as session:
        application = session.get(Application, application_id)
        assert application is not None
        assert application.status == "AUTO_BIND"


def test_lost_number_race_is_retried(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A colliding sequence is retried: the UNIQUE constraint decides, the caller still gets 201."""
    first = auto_bind_application(api_client)
    second = auto_bind_application(api_client)
    actor = _Actor("cust-001", ActorRole.CUSTOMER)
    with Session(seeded_engine) as session:
        PolicyService(session).issue(first, actor)
    real = PolicyRepository.next_sequence
    calls: list[int] = []

    def _stale(self: PolicyRepository, prefix: str, year: int) -> int:
        calls.append(1)
        return 1 if len(calls) == 1 else int(real(self, prefix, year))

    monkeypatch.setattr(PolicyRepository, "next_sequence", _stale)
    with Session(seeded_engine) as session:
        view = PolicyService(session).issue(second, actor)
    assert view.policy_number == "MO-2026-000002"
    assert len(calls) == 2
    assert _count(seeded_engine, Policy) == 2


def test_duplicate_policy_number_is_rejected_by_the_unique_constraint(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """A raw insert of an existing policy number raises IntegrityError."""
    application_id = auto_bind_application(api_client)
    with Session(seeded_engine) as session:
        policy = PolicyService(session).issue(
            application_id, _Actor("cust-001", ActorRole.CUSTOMER)
        )
    with Session(seeded_engine) as session:
        existing = session.execute(select(Policy)).scalars().one()
        clone = Policy(
            policy_number=policy.policy_number,
            product=existing.product,
            application_id=existing.application_id,
            customer_id=existing.customer_id,
            rule_version=existing.rule_version,
            rating_inputs=dict(existing.rating_inputs),
            sum_insured=existing.sum_insured,
            premium=existing.premium,
            effective_date=existing.effective_date,
            expiry_date=existing.expiry_date,
            premium_due_date=existing.premium_due_date,
            status=existing.status,
            address=existing.address,
            nominees=[],
        )
        session.add(clone)
        with pytest.raises(IntegrityError):
            session.commit()
