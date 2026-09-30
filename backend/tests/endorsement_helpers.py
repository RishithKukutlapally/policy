"""Shared helpers for the endorsement API tests (synthetic data only)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository.models import AuditRecord, Endorsement, Policy, PolicyStateTransition
from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.policy_helpers import ISSUE_DATE, auto_bind_application, issue_ok

#: 184 days after ISSUE_DATE: 181 of the 365 term days are unused (AC-16 worked case).
ENDORSE_DATE = "2026-09-01"

SUM_BODY = {"type": "CHANGE_SUM_INSURED", "new_sum_insured": "600000.00"}
ADDRESS_BODY = {"type": "CHANGE_ADDRESS", "address": "2 Sample Road, Testville"}
NOMINEE_BODY = {
    "type": "ADD_NOMINEE",
    "nominee_name": "Test Nominee",
    "relationship": "SPOUSE",
    "share_percent": "60",
}


def issued_policy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    """Issue a MOTOR policy (500000.00 / 15500.00); leave the clock on ENDORSE_DATE."""
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ISSUE_DATE)
    number = str(issue_ok(client, auto_bind_application(client))["policy_number"])
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ENDORSE_DATE)
    return number


def endorse(
    client: TestClient,
    policy_number: str,
    body: dict[str, Any],
    *,
    role: ActorRole = ActorRole.CUSTOMER,
    preview: bool = False,
) -> httpx.Response:
    """POST an endorsement (or its preview)."""
    return client.post(
        f"/api/policies/{policy_number}/endorsements",
        json=body,
        params={"preview": "true"} if preview else None,
        headers=actor_headers(role),
    )


def count(engine: Engine, model: type[Any]) -> int:
    """Row count of ``model``'s table."""
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def policy_row(engine: Engine, policy_number: str) -> Policy:
    """The policy row, loaded and detached."""
    with Session(engine, expire_on_commit=False) as session:
        statement = select(Policy).where(Policy.policy_number == policy_number)
        return session.execute(statement).scalar_one()


def endorsement_rows(engine: Engine) -> list[Endorsement]:
    """Every endorsement row."""
    with Session(engine, expire_on_commit=False) as session:
        return list(session.execute(select(Endorsement)).scalars())


def transition_rows(engine: Engine) -> list[PolicyStateTransition]:
    """Every transition row."""
    with Session(engine, expire_on_commit=False) as session:
        return list(session.execute(select(PolicyStateTransition)).scalars())


def audit_rows(engine: Engine, action: str) -> list[AuditRecord]:
    """Audit rows of ``action``."""
    with Session(engine, expire_on_commit=False) as session:
        statement = select(AuditRecord).where(AuditRecord.action == action)
        return list(session.execute(statement).scalars())
