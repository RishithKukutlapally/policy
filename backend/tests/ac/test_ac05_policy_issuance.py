"""AC-05: issuance turns an AUTO_BIND application into an ACTIVE policy (E5-S2, E5-S3)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.types.enums import ActorRole
from tests.application_helpers import motor_application
from tests.conftest import actor_headers
from tests.policy_helpers import (
    ISSUE_DATE,
    auto_bind_application,
    household_application,
    issue,
    issue_ok,
    policies,
    policy_audit_rows,
    transitions,
)

pytestmark = pytest.mark.ac("AC-05")

POLICY_NUMBER = re.compile(r"^(TL|MO|HH)-\d{4}-\d{6}$")


@pytest.fixture(name="business_date", autouse=True)
def _business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the business date on the golden issuance day (DEC-012)."""
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ISSUE_DATE)


def test_ac05_issue_auto_bind_application_creates_active_policy(api_client: TestClient) -> None:
    """The golden MOTOR case: 500000.00 x 0.0310 = 15500.00, 12-month term from 2026-03-01."""
    body = issue_ok(api_client, auto_bind_application(api_client))
    assert POLICY_NUMBER.match(body["policy_number"]), body
    assert body["status"] == "ACTIVE"
    assert body["product"] == "MOTOR"
    assert body["rule_version"] == 1
    assert body["sum_insured"] == "500000.00"
    assert body["premium"] == "15500.00"
    assert body["currency"] == "INR"
    assert body["effective_date"] == "2026-03-01"
    assert body["expiry_date"] == "2027-02-28"
    assert body["premium_due_date"] == "2026-03-01"
    assert body["next_premium_due_date"] == "2027-03-01"
    assert body["previous_policy_number"] is None


def test_ac05_policy_numbers_increment_per_product_and_year(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """Sequences are allocated per prefix and year: MO-2026-000001/2 and HH-2026-000001."""
    first = issue_ok(api_client, auto_bind_application(api_client))["policy_number"]
    second = issue_ok(api_client, auto_bind_application(api_client))["policy_number"]
    household = issue_ok(api_client, household_application(api_client))["policy_number"]
    assert [first, second, household] == ["MO-2026-000001", "MO-2026-000002", "HH-2026-000001"]
    numbers = {row.policy_number for row in policies(seeded_engine)}
    assert numbers == {first, second, household}
    assert all(POLICY_NUMBER.match(number) for number in numbers)


def test_ac05_premium_and_sum_insured_are_two_decimal_decimals(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """Money is stored as Decimal quantized to 0.01 — never float (NFR-01)."""
    issue_ok(api_client, auto_bind_application(api_client))
    (row,) = policies(seeded_engine)
    assert isinstance(row.premium, Decimal)
    assert isinstance(row.sum_insured, Decimal)
    assert row.premium == Decimal("15500.00")
    assert row.premium.as_tuple().exponent == -2


def test_ac05_issuing_twice_is_rejected(api_client: TestClient, seeded_engine: Engine) -> None:
    """The application is ISSUED after the first call, so the second is 409."""
    application_id = auto_bind_application(api_client)
    issue_ok(api_client, application_id)
    response = issue(api_client, application_id, role=ActorRole.CUSTOMER)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_APPLICATION_STATE"
    assert len(policies(seeded_engine)) == 1


@pytest.mark.parametrize(("vehicle_age_years", "status"), [(12, "MANUAL_REVIEW"), (16, "DECLINED")])
def test_ac05_non_auto_bind_application_persists_nothing(
    api_client: TestClient, seeded_engine: Engine, vehicle_age_years: int, status: str
) -> None:
    """MANUAL_REVIEW / DECLINED applications cannot be issued and consume no number."""
    application_id = motor_application(api_client, vehicle_age_years)
    detail = api_client.get(
        f"/api/applications/{application_id}", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert detail.json()["status"] == status
    response = issue(api_client, application_id, role=ActorRole.CUSTOMER)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_APPLICATION_STATE"
    assert policies(seeded_engine) == []
    assert transitions(seeded_engine) == []


def test_ac05_issuance_writes_one_transition_and_audit_row(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """Exactly one NULL -> ACTIVE transition and one POLICY_ISSUED audit row for an ADMIN."""
    application_id = auto_bind_application(api_client)
    body = issue_ok(api_client, application_id, role=ActorRole.ADMIN)
    (transition,) = transitions(seeded_engine)
    assert transition.from_status is None
    assert transition.to_status == "ACTIVE"
    assert transition.reason == "ISSUED"
    assert transition.actor_id == "admin-001"
    assert transition.occurred_at is not None
    (record,) = policy_audit_rows(seeded_engine, body["policy_number"])
    assert record.action == "POLICY_ISSUED"
    assert record.entity_type == "POLICY"
    assert record.actor_id == "admin-001"
    assert record.actor_role == "ADMIN"


def test_ac05_issuance_records_the_first_term_premium_payment(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """One premium_payments row for the first term, due on the effective date."""
    body = issue_ok(api_client, auto_bind_application(api_client))
    detail = api_client.get(
        f"/api/policies/{body['policy_number']}", headers=actor_headers(ActorRole.CUSTOMER)
    ).json()
    assert [(p["due_date"], p["amount"]) for p in detail["payments"]] == [
        ("2026-03-01", "15500.00")
    ]


def test_ac05_application_moves_to_issued(api_client: TestClient) -> None:
    """The application status projection moves to ISSUED in the issuing transaction."""
    application_id = auto_bind_application(api_client)
    issue_ok(api_client, application_id)
    detail = api_client.get(
        f"/api/applications/{application_id}", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert detail.json()["status"] == "ISSUED"


def test_ac05_issue_requires_actor_headers(api_client: TestClient) -> None:
    """No actor headers -> 401 UNAUTHENTICATED; UNDERWRITER -> 403 FORBIDDEN."""
    application_id = auto_bind_application(api_client)
    anonymous = api_client.post(f"/api/applications/{application_id}/issue")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "UNAUTHENTICATED"
    underwriter = issue(api_client, application_id, role=ActorRole.UNDERWRITER)
    assert underwriter.status_code == 403


def test_ac05_another_customers_application_is_not_found(api_client: TestClient) -> None:
    """Owner scoping: a foreign application is 404, never 409 or 403 (no existence leak)."""
    application_id = auto_bind_application(api_client)
    response = issue(api_client, application_id, role=ActorRole.CUSTOMER, actor_id="cust-002")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
