"""AC-07: renewal quote, renewal into a linked successor term, and lapse after the grace period."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.renewal_helpers import (
    DUE_DATE,
    GRACE_END,
    IN_WINDOW,
    PREMIUM,
    WINDOW_OPENS,
    issue_policy,
    pay,
    run_end_of_day,
    status_of,
)

pytestmark = pytest.mark.ac("AC-07")


def _renewal(
    client: TestClient, number: str, role: ActorRole = ActorRole.CUSTOMER
) -> httpx.Response:
    return client.get(f"/api/policies/{number}/renewal", headers=actor_headers(role))


def test_ac07_renewal_quote_inside_window(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refreshed premium on the active version, with due / grace dates and the window opening."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    response = _renewal(api_client, number)
    assert response.status_code == 200, response.text
    body = response.json()
    # 500000.00 x 0.0310 x 1.00 (vehicle age 3, band 0-5) x 1.00 x 1.00 x (1 - 0.00) = 15500.00
    assert body["renewal_premium"] == PREMIUM
    assert body["renewable"] is True
    assert body["rule_version"] == 1
    assert body["due_date"] == DUE_DATE
    assert body["grace_end_date"] == GRACE_END
    assert body["renewal_window_opens"] == WINDOW_OPENS
    assert body["paid"] is False
    assert _renewal(api_client, number, ActorRole.ADMIN).status_code == 200


def test_ac07_renewal_quote_before_window_is_409(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before expiry - 30 days the quote is refused."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "2026-12-01")
    response = _renewal(api_client, number)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUTSIDE_RENEWAL_WINDOW"


def test_ac07_renew_after_payment_creates_linked_successor(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The successor is ACTIVE, linked by previous_policy_number; the old policy is RENEWED."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    assert pay(api_client, number).status_code == 201
    headers = actor_headers(ActorRole.CUSTOMER)
    response = api_client.post(f"/api/policies/{number}/renew", headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["policy_number"] == "MO-2027-000001"
    assert body["previous_policy_number"] == number
    assert body["status"] == "ACTIVE"
    assert body["premium"] == PREMIUM
    assert body["rule_version"] == 1
    assert body["effective_date"] == "2027-03-01"
    assert body["expiry_date"] == "2028-02-29"
    assert status_of(seeded_engine, number) == "RENEWED"
    detail = api_client.get(f"/api/policies/{number}", headers=headers).json()
    assert detail["successor_policy_number"] == "MO-2027-000001"
    assert [t["to_status"] for t in detail["transitions"]] == ["ACTIVE", "RENEWED"]
    successor = api_client.get("/api/policies/MO-2027-000001", headers=headers).json()
    assert [(t["from_status"], t["to_status"]) for t in successor["transitions"]] == [
        (None, "ACTIVE")
    ]
    again = api_client.post(f"/api/policies/{number}/renew", headers=headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVALID_POLICY_STATE"


def test_ac07_renew_without_payment_or_outside_window(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unpaid -> 422 RENEWAL_PREMIUM_UNPAID; before the window -> 409 OUTSIDE_RENEWAL_WINDOW."""
    number = issue_policy(api_client, monkeypatch)
    headers = actor_headers(ActorRole.CUSTOMER)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    unpaid = api_client.post(f"/api/policies/{number}/renew", headers=headers)
    assert unpaid.status_code == 422
    assert unpaid.json()["error"]["details"] == [
        {"field": "payment", "code": "RENEWAL_PREMIUM_UNPAID"}
    ]
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "2026-12-01")
    early = api_client.post(f"/api/policies/{number}/renew", headers=headers)
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "OUTSIDE_RENEWAL_WINDOW"


def test_ac07_unpaid_policy_lapses_after_grace_period(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Untouched on the last grace day (2027-03-31), LAPSED the day after."""
    number = issue_policy(api_client, monkeypatch)
    assert run_end_of_day(api_client, GRACE_END).json()["lapsed"] == 0
    assert status_of(seeded_engine, number) == "ACTIVE"
    result = run_end_of_day(api_client, "2027-04-01")
    assert result.json()["lapsed"] == 1
    assert status_of(seeded_engine, number) == "LAPSED"
