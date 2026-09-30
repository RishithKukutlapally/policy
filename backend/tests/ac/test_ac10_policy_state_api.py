"""AC-10: a lifecycle action on a terminal policy is refused and changes nothing (E5-S2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.repository.policy_repository import PolicyRepository
from src.service.policy_service import PolicyService
from src.types.enums import ActorRole, PolicyStatus
from src.types.errors import InvalidPolicyStateException, NotFoundError
from tests.conftest import actor_headers
from tests.policy_helpers import ISSUE_DATE, auto_bind_application, issue_ok, transitions

pytestmark = pytest.mark.ac("AC-10")


@pytest.fixture(name="business_date", autouse=True)
def _business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the business date on the golden issuance day (DEC-012)."""
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ISSUE_DATE)


class _Actor:
    """Minimal stand-in for the API layer's ``Actor`` (structural, no `src.api` import)."""

    def __init__(self, actor_id: str, role: ActorRole) -> None:
        self.actor_id = actor_id
        self.role = role


@pytest.fixture(name="cancelled_policy")
def _cancelled_policy(api_client: TestClient, seeded_engine: Engine) -> str:
    """Issue a policy and seed it directly into the terminal CANCELLED state."""
    number = str(issue_ok(api_client, auto_bind_application(api_client))["policy_number"])
    with Session(seeded_engine) as session:
        policies = PolicyRepository(session)
        policy = policies.get_by_number(number)
        assert policy is not None
        policies.update_projection(policy, status=PolicyStatus.CANCELLED)
        session.commit()
    return number


def test_ac10_lifecycle_action_on_terminal_policy_is_rejected(
    cancelled_policy: str, seeded_engine: Engine
) -> None:
    """A CANCELLED policy has no outgoing transition: 409 INVALID_POLICY_STATE, nothing changes."""
    before = len(transitions(seeded_engine))
    with Session(seeded_engine) as session:
        service = PolicyService(session)
        with pytest.raises(InvalidPolicyStateException) as raised:
            service.transition(
                cancelled_policy,
                PolicyStatus.ENDORSED,
                reason="ENDORSEMENT:CHANGE_ADDRESS",
                actor=_Actor("cust-001", ActorRole.CUSTOMER),
            )
    assert raised.value.code == "INVALID_POLICY_STATE"
    assert raised.value.http_status == 409
    assert raised.value.details == {"current": "CANCELLED", "target": "ENDORSED"}
    assert len(transitions(seeded_engine)) == before
    with Session(seeded_engine) as session:
        policy = PolicyRepository(session).get_by_number(cancelled_policy)
        assert policy is not None
        assert policy.status == PolicyStatus.CANCELLED.value


def test_ac10_terminal_policy_still_readable(api_client: TestClient, cancelled_policy: str) -> None:
    """Reads keep working: the detail view reports the terminal status."""
    response = api_client.get(
        f"/api/policies/{cancelled_policy}", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"


def test_ac10_allowed_transition_appends_one_row(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """ACTIVE -> ENDORSED is allowed: the projection moves and exactly one row is appended."""
    number = str(issue_ok(api_client, auto_bind_application(api_client))["policy_number"])
    before = len(transitions(seeded_engine))
    with Session(seeded_engine) as session:
        PolicyService(session).transition(
            number,
            PolicyStatus.ENDORSED,
            reason="ENDORSEMENT:CHANGE_ADDRESS",
            actor=_Actor("cust-001", ActorRole.CUSTOMER),
        )
        session.commit()
    assert len(transitions(seeded_engine)) == before + 1
    with Session(seeded_engine) as session:
        policy = PolicyRepository(session).get_by_number(number)
        assert policy is not None
        assert policy.status == PolicyStatus.ENDORSED.value


def test_ac10_transition_on_a_foreign_or_unknown_policy_is_not_found(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """Owner scoping applies to lifecycle actions too: 404, never 409."""
    number = str(issue_ok(api_client, auto_bind_application(api_client))["policy_number"])
    with Session(seeded_engine) as session:
        service = PolicyService(session)
        for policy_number, actor_id in ((number, "cust-002"), ("MO-2026-999999", "cust-001")):
            with pytest.raises(NotFoundError):
                service.transition(
                    policy_number,
                    PolicyStatus.CANCELLED,
                    reason="CANCELLED:test",
                    actor=_Actor(actor_id, ActorRole.CUSTOMER),
                )
