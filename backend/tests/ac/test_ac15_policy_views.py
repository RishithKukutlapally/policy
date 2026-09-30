"""AC-15: My Policies list and Policy Detail read models (E5-S3)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.types.enums import ActorRole, EndorsementType, PolicyStatus
from tests.conftest import actor_headers
from tests.policy_helpers import ISSUE_DATE, auto_bind_application, issue_ok

pytestmark = pytest.mark.ac("AC-15")


@pytest.fixture(name="business_date", autouse=True)
def _business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the business date on the golden issuance day (DEC-012)."""
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ISSUE_DATE)


def _issue_for(client: TestClient, actor_id: str) -> str:
    """Issue one MOTOR policy owned by ``actor_id`` and return its number."""
    application_id = auto_bind_application(client, actor_id=actor_id)
    body = issue_ok(client, application_id, actor_id=actor_id)
    return str(body["policy_number"])


def _list_policies(client: TestClient, role: ActorRole, actor_id: str | None = None) -> list[dict]:
    """GET /api/policies as ``role`` and assert 200."""
    response = client.get("/api/policies", headers=actor_headers(role, actor_id))
    assert response.status_code == 200, response.text
    items: list[dict] = response.json()
    return items


def test_ac15_customer_sees_only_their_own_policies(api_client: TestClient) -> None:
    """Two policies for cust-001 and one for cust-002: the owner sees exactly two."""
    mine = {_issue_for(api_client, "cust-001"), _issue_for(api_client, "cust-001")}
    theirs = _issue_for(api_client, "cust-002")
    items = _list_policies(api_client, ActorRole.CUSTOMER, "cust-001")
    assert {item["policy_number"] for item in items} == mine
    assert theirs not in {item["policy_number"] for item in items}
    first = items[0]
    assert first["product"] == "MOTOR"
    assert first["status"] == "ACTIVE"
    assert first["sum_insured"] == "500000.00"
    assert first["premium"] == "15500.00"
    assert first["effective_date"] == "2026-03-01"
    assert first["expiry_date"] == "2027-02-28"
    assert first["next_premium_due_date"] == "2027-03-01"


def test_ac15_underwriter_sees_every_policy(api_client: TestClient) -> None:
    """UNDERWRITER and ADMIN are not owner-scoped."""
    numbers = {_issue_for(api_client, "cust-001"), _issue_for(api_client, "cust-002")}
    seen = {item["policy_number"] for item in _list_policies(api_client, ActorRole.UNDERWRITER)}
    assert numbers <= seen
    assert seen == {item["policy_number"] for item in _list_policies(api_client, ActorRole.ADMIN)}


def test_ac15_list_is_ordered_and_filterable(api_client: TestClient) -> None:
    """Ordered by effective_date then policy_number; unknown filter values are 422."""
    _issue_for(api_client, "cust-001")
    _issue_for(api_client, "cust-001")
    items = _list_policies(api_client, ActorRole.CUSTOMER, "cust-001")
    assert [i["policy_number"] for i in items] == sorted(i["policy_number"] for i in items)
    filtered = api_client.get(
        "/api/policies?product=MOTOR&status=ACTIVE", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 2
    empty = api_client.get(
        "/api/policies?status=CANCELLED", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert empty.json() == []
    unknown = api_client.get(
        "/api/policies?product=BOAT", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["details"][0]["code"] == "UNKNOWN_CODE"


def _seed_history(engine: Engine, policy_number: str) -> None:
    """Append two endorsements and two further transitions to ``policy_number``."""
    with Session(engine) as session:
        policy = PolicyRepository(session).get_by_number(policy_number)
        assert policy is not None
        lifecycle = PolicyLifecycleRepository(session)
        for index, change in enumerate(("1 Sample Street, Testville", "7 Example Road, Demotown")):
            lifecycle.add_endorsement(
                policy_id=policy.id,
                endorsement_type=EndorsementType.CHANGE_ADDRESS,
                before={"address": "1 Sample Street, Testville"},
                after={"address": change},
                premium_delta=Decimal("0.00"),
                rule_version=policy.rule_version,
                endorsement_date=policy.effective_date,
                actor_id="cust-001",
            )
            lifecycle.add_transition(
                policy_id=policy.id,
                from_status=PolicyStatus.ACTIVE if index == 0 else PolicyStatus.ENDORSED,
                to_status=PolicyStatus.ENDORSED,
                reason="ENDORSEMENT:CHANGE_ADDRESS",
                actor_id="cust-001",
            )
        session.commit()


def test_ac15_detail_exposes_history_transitions_and_payments(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """Detail carries endorsements (oldest first), transitions, payments and refunds."""
    number = _issue_for(api_client, "cust-001")
    _seed_history(seeded_engine, number)
    response = api_client.get(f"/api/policies/{number}", headers=actor_headers(ActorRole.CUSTOMER))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["policy_number"] == number
    assert body["application_id"]
    assert body["insured"]["aadhaar_masked"] == "XXXX-XXXX-0001"
    assert body["insured"]["nominees"] == []
    assert [e["after"]["address"] for e in body["endorsements"]] == [
        "1 Sample Street, Testville",
        "7 Example Road, Demotown",
    ]
    assert [e["premium_delta"] for e in body["endorsements"]] == ["0.00", "0.00"]
    assert [(t["from_status"], t["to_status"]) for t in body["transitions"]] == [
        (None, "ACTIVE"),
        ("ACTIVE", "ENDORSED"),
        ("ENDORSED", "ENDORSED"),
    ]
    assert len(body["payments"]) == 1
    assert body["refunds"] == []
    assert body["successor_policy_number"] is None


def test_ac15_another_customers_policy_is_not_found(api_client: TestClient) -> None:
    """A foreign policy and an unknown number are both 404 NOT_FOUND."""
    number = _issue_for(api_client, "cust-001")
    foreign = api_client.get(
        f"/api/policies/{number}", headers=actor_headers(ActorRole.CUSTOMER, "cust-002")
    )
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "NOT_FOUND"
    unknown = api_client.get(
        "/api/policies/MO-2026-999999", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert unknown.status_code == 404


def test_ac15_detail_is_open_to_staff(api_client: TestClient) -> None:
    """UNDERWRITER and ADMIN may read any policy; anonymous callers get 401."""
    number = _issue_for(api_client, "cust-001")
    for role in (ActorRole.UNDERWRITER, ActorRole.ADMIN):
        response = api_client.get(f"/api/policies/{number}", headers=actor_headers(role))
        assert response.status_code == 200, response.text
    assert api_client.get(f"/api/policies/{number}").status_code == 401
    assert api_client.get("/api/policies").status_code == 401
