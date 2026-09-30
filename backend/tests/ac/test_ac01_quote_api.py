"""AC-01 over HTTP: POST /api/quotes prices from the active PUBLISHED rule version."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.quote_helpers import motor_request


@pytest.mark.ac("AC-01")
def test_ac01_motor_quote_returns_golden_premium_and_records_version(
    api_client: TestClient,
) -> None:
    """AC-01: MOTOR 500000 / 35 / 3 / 1200 / A / 20 -> 14322.00 on rule version 1."""
    response = api_client.post(
        "/api/quotes", json=motor_request(), headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["premium"] == "14322.00"
    assert body["rule_version"] == 1
    assert body["product"] == "MOTOR"
    assert body["currency"] == "INR"
    assert body["sum_insured"] == "500000.00"
    assert len(body["quote_id"]) == 36


@pytest.mark.ac("AC-01")
def test_ac01_same_request_twice_gives_identical_premium(api_client: TestClient) -> None:
    """AC-01: determinism - two identical requests, identical premium and version."""
    headers = actor_headers(ActorRole.CUSTOMER)
    first = api_client.post("/api/quotes", json=motor_request(), headers=headers).json()
    second = api_client.post("/api/quotes", json=motor_request(), headers=headers).json()
    assert first["premium"] == second["premium"] == "14322.00"
    assert first["quote_id"] != second["quote_id"]


@pytest.mark.ac("AC-01")
def test_ac01_only_customers_may_create_quotes(api_client: TestClient) -> None:
    """AC-01: UNDERWRITER and ADMIN get 403 on POST /api/quotes."""
    for role in (ActorRole.UNDERWRITER, ActorRole.ADMIN):
        response = api_client.post("/api/quotes", json=motor_request(), headers=actor_headers(role))
        assert response.status_code == 403


@pytest.mark.ac("AC-01")
def test_ac01_get_quote_owner_only(api_client: TestClient) -> None:
    """AC-01: the owner and staff can read a quote; another customer gets 404."""
    created = api_client.post(
        "/api/quotes", json=motor_request(), headers=actor_headers(ActorRole.CUSTOMER)
    ).json()
    path = f"/api/quotes/{created['quote_id']}"
    owner = api_client.get(path, headers=actor_headers(ActorRole.CUSTOMER))
    assert owner.status_code == 200
    assert owner.json()["premium"] == "14322.00"
    assert owner.json()["actor_id"] == "cust-001"
    assert api_client.get(path, headers=actor_headers(ActorRole.ADMIN)).status_code == 200
    other = api_client.get(path, headers=actor_headers(ActorRole.CUSTOMER, "cust-002"))
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "NOT_FOUND"
    missing = api_client.get("/api/quotes/not-a-uuid", headers=actor_headers(ActorRole.CUSTOMER))
    assert missing.status_code == 404
