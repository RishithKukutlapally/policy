"""The lifecycle tables round-trip through their append-only repositories (NFR-01, NFR-02)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.types.enums import RefundType
from tests.policy_helpers import ISSUE_DATE, auto_bind_application, issue_ok

pytestmark = pytest.mark.integration


@pytest.fixture(name="business_date", autouse=True)
def _business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the business date on the golden issuance day (DEC-012)."""
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ISSUE_DATE)


@pytest.fixture(name="policy_number")
def _policy_number(api_client: TestClient) -> str:
    """One issued MOTOR policy."""
    return str(issue_ok(api_client, auto_bind_application(api_client))["policy_number"])


def test_refund_round_trips_as_decimal(policy_number: str, seeded_engine: Engine) -> None:
    """A refund row keeps its money as Decimal and is read back by policy."""
    with Session(seeded_engine) as session:
        policy = PolicyRepository(session).get_by_number(policy_number)
        assert policy is not None
        lifecycle = PolicyLifecycleRepository(session)
        lifecycle.add_refund(
            policy_id=policy.id,
            refund_type=RefundType.PRO_RATA,
            premium_paid=Decimal("15500.00"),
            term_days=365,
            days_elapsed=90,
            unused_days=275,
            admin_fee=Decimal("250.00"),
            amount=Decimal("11430.14"),
            rule_version=policy.rule_version,
            cancellation_date=policy.effective_date,
            reason="NO_LONGER_NEEDED",
            actor_id="cust-001",
        )
        session.commit()
    with Session(seeded_engine) as session:
        policy = PolicyRepository(session).get_by_number(policy_number)
        assert policy is not None
        (refund,) = PolicyLifecycleRepository(session).refunds_of(policy.id)
    assert refund.amount == Decimal("11430.14")
    assert isinstance(refund.amount, Decimal)
    assert refund.unused_days == refund.term_days - refund.days_elapsed


def test_update_projection_moves_endorsable_attributes(
    policy_number: str, seeded_engine: Engine
) -> None:
    """The projection may move its endorsable attributes; unknown names are refused."""
    with Session(seeded_engine) as session:
        policies = PolicyRepository(session)
        policy = policies.get_by_number(policy_number)
        assert policy is not None
        changes = {"address": "7 Example Road, Demotown", "premium": Decimal("18600.00")}
        policies.update_projection(policy, attributes=changes)
        session.commit()
        with pytest.raises(AttributeError):
            policies.update_projection(policy, attributes={"not_a_column": 1})
    with Session(seeded_engine) as session:
        moved = PolicyRepository(session).get_by_number(policy_number)
        assert moved is not None
        assert moved.address == "7 Example Road, Demotown"
        assert moved.premium == Decimal("18600.00")
