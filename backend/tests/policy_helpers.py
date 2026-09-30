"""Shared helpers for the policy issuance / policy view tests (synthetic data only)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from src.repository.models import AuditRecord, Policy, PolicyStateTransition
from src.types.enums import ActorRole
from tests.application_helpers import KYC, application_for, submit
from tests.conftest import actor_headers
from tests.quote_helpers import motor_request

#: Business date used by every issuance golden case (E5-S2 AC-1).
ISSUE_DATE = "2026-03-01"


def auto_bind_application(client: TestClient, *, actor_id: str | None = None) -> str:
    """Submit a MOTOR application that auto-binds and return its id."""
    body = motor_request(vehicle_age_years=2, engine_cc=998, zone="B", ncb_percent="0")
    response = submit(client, create_quote_as(client, body, actor_id), actor_id=actor_id)
    assert response.status_code == 201, response.text
    payload: dict[str, Any] = response.json()
    assert payload["status"] == "AUTO_BIND", payload
    return str(payload["application_id"])


def create_quote_as(client: TestClient, body: dict[str, Any], actor_id: str | None) -> str:
    """Create a quote for ``actor_id`` (defaults to the demo customer) and return its id."""
    response = client.post(
        "/api/quotes", json=body, headers=actor_headers(ActorRole.CUSTOMER, actor_id)
    )
    assert response.status_code == 201, response.text
    return str(response.json()["quote_id"])


def household_application(client: TestClient) -> str:
    """Submit a HOUSEHOLD application that auto-binds and return its id."""
    body = application_for(client, "HOUSEHOLD")
    assert body["status"] == "AUTO_BIND", body
    return str(body["application_id"])


def issue(
    client: TestClient, application_id: str, *, role: ActorRole, actor_id: str | None = None
) -> httpx.Response:
    """POST the issue endpoint and return the raw response."""
    return client.post(
        f"/api/applications/{application_id}/issue", headers=actor_headers(role, actor_id)
    )


def issue_ok(client: TestClient, application_id: str, **kwargs: Any) -> dict[str, Any]:
    """Issue ``application_id`` and assert 201, returning the response body."""
    response = issue(client, application_id, role=kwargs.pop("role", ActorRole.CUSTOMER), **kwargs)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def policies(engine: Engine) -> list[Policy]:
    """Every persisted policy row."""
    with Session(engine) as session:
        return list(session.execute(select(Policy)).scalars())


def transitions(engine: Engine) -> list[PolicyStateTransition]:
    """Every persisted transition row."""
    with Session(engine) as session:
        return list(session.execute(select(PolicyStateTransition)).scalars())


def policy_audit_rows(engine: Engine, policy_number: str) -> list[AuditRecord]:
    """Audit rows recorded against ``policy_number``."""
    with Session(engine) as session:
        statement = select(AuditRecord).where(AuditRecord.entity_id == policy_number)
        return list(session.execute(statement).scalars())


__all__ = [
    "ISSUE_DATE",
    "KYC",
    "auto_bind_application",
    "create_quote_as",
    "household_application",
    "issue",
    "issue_ok",
    "policies",
    "policy_audit_rows",
    "transitions",
]
