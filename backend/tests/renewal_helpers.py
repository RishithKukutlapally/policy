"""Shared helpers for the renewal, payment, end-of-day and cancellation tests (synthetic data).

Every helper policy is a MOTOR policy issued on ``ISSUE_DATE`` (2026-03-01): premium ``15500.00``
(``500000.00 x 0.0310 x 1.00 x 1.00 x 1.00 x (1 - 0.00)``: vehicle 2 years, 998 cc, zone B,
NCB 0), term 2026-03-01 to 2027-02-28, renewal due
2027-03-01, grace end 2027-03-31.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository.models import (
    AuditRecord,
    Policy,
    PolicyStateTransition,
    PremiumPayment,
    Refund,
)
from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.policy_helpers import ISSUE_DATE, auto_bind_application, issue_ok

PREMIUM = "15500.00"
DUE_DATE = "2027-03-01"
GRACE_END = "2027-03-31"
WINDOW_OPENS = "2027-01-29"
IN_WINDOW = "2027-02-15"


def issue_policy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, *, actor_id: str | None = None
) -> str:
    """Issue a fresh MOTOR policy on ``ISSUE_DATE`` and return its number."""
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", ISSUE_DATE)
    body = issue_ok(client, auto_bind_application(client, actor_id=actor_id), actor_id=actor_id)
    return str(body["policy_number"])


def pay(
    client: TestClient, number: str, amount: str = PREMIUM, *, actor_id: str | None = None
) -> httpx.Response:
    """POST a renewal-premium payment as the (default) demo customer."""
    return client.post(
        f"/api/policies/{number}/payments",
        json={"amount": amount},
        headers=actor_headers(ActorRole.CUSTOMER, actor_id),
    )


def run_end_of_day(client: TestClient, as_of: str) -> httpx.Response:
    """POST the admin end-of-day trigger."""
    return client.post(
        "/api/admin/end-of-day", json={"as_of": as_of}, headers=actor_headers(ActorRole.ADMIN)
    )


def cancel(
    client: TestClient,
    number: str,
    cancellation_date: str,
    *,
    reason: str = "Vehicle sold",
    role: ActorRole = ActorRole.CUSTOMER,
    actor_id: str | None = None,
) -> httpx.Response:
    """POST the cancel endpoint."""
    return client.post(
        f"/api/policies/{number}/cancel",
        json={"cancellation_date": cancellation_date, "reason": reason},
        headers=actor_headers(role, actor_id),
    )


def status_of(engine: Engine, number: str) -> str:
    """Stored status of ``number``."""
    with Session(engine) as session:
        return session.execute(
            select(Policy.status).where(Policy.policy_number == number)
        ).scalar_one()


def count(engine: Engine, model: type[Any]) -> int:
    """Row count of one mapped table."""
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def counts(engine: Engine) -> dict[str, int]:
    """Row counts of every table an end-of-day run may touch."""
    return {
        "policies": count(engine, Policy),
        "transitions": count(engine, PolicyStateTransition),
        "payments": count(engine, PremiumPayment),
        "refunds": count(engine, Refund),
    }


def audit_rows(engine: Engine, action: str) -> list[AuditRecord]:
    """Audit rows with ``action``."""
    with Session(engine) as session:
        statement = select(AuditRecord).where(AuditRecord.action == action)
        return list(session.execute(statement).scalars())
