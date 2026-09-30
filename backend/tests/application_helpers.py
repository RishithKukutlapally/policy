"""Shared helpers for the application / underwriting API tests (synthetic data only)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from src.repository.models import AuditRecord
from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.quote_helpers import motor_request

KYC: dict[str, Any] = {
    "full_name": "Test Customer 01",
    "date_of_birth": "1996-04-01",
    "aadhaar": "999900000001",
    "pan": "AAAAA0001A",
    "address": "1 Sample Street, Testville",
}
TERM_LIFE_INPUTS: dict[str, Any] = {
    "sum_insured": "1000000.00",
    "age": 35,
    "term_years": 20,
    "smoker": False,
}
HOUSEHOLD_INPUTS: dict[str, Any] = {
    "sum_insured": "1000000.00",
    "proposer_age": 40,
    "construction_type": "CONCRETE",
    "in_flood_zone": False,
    "has_security_system": True,
}
HEALTH_CLEAR: dict[str, Any] = {"has_pre_existing_condition": False}


def create_quote(client: TestClient, body: dict[str, Any]) -> str:
    """Create a quote as the demo customer and return its id."""
    response = client.post("/api/quotes", json=body, headers=actor_headers(ActorRole.CUSTOMER))
    assert response.status_code == 201, response.text
    return str(response.json()["quote_id"])


def submit(
    client: TestClient,
    quote_id: str,
    *,
    kyc: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    actor_id: str | None = None,
) -> Any:
    """POST /api/applications for ``quote_id`` and return the raw response."""
    body: dict[str, Any] = {"quote_id": quote_id, "kyc": kyc or KYC}
    if health is not None:
        body["health_declaration"] = health
    return client.post(
        "/api/applications", json=body, headers=actor_headers(ActorRole.CUSTOMER, actor_id)
    )


def application_for(client: TestClient, product: str, **overrides: Any) -> dict[str, Any]:
    """Quote and submit one application of ``product``; ``overrides`` tweak the rating inputs."""
    health: dict[str, Any] | None = None
    if product == "MOTOR":
        body = motor_request(**overrides)
    elif product == "TERM_LIFE":
        body = {"product": product, "inputs": {**TERM_LIFE_INPUTS, **overrides}}
        health = HEALTH_CLEAR
    else:
        body = {"product": product, "inputs": {**HOUSEHOLD_INPUTS, **overrides}}
    response = submit(client, create_quote(client, body), health=health)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def motor_application(client: TestClient, vehicle_age_years: int) -> str:
    """Submit a MOTOR application; 3 -> AUTO_BIND, 12 -> MANUAL_REVIEW, 16 -> DECLINED."""
    body = application_for(client, "MOTOR", vehicle_age_years=vehicle_age_years)
    return str(body["application_id"])


def audit_rows(engine: Engine, application_id: str) -> list[AuditRecord]:
    """Every audit row recorded for ``application_id``."""
    with Session(engine) as session:
        statement = select(AuditRecord).where(AuditRecord.entity_id == application_id)
        return list(session.execute(statement).scalars())
