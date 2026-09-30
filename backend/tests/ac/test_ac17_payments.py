"""AC-17: simulated renewal-premium payments are append-only and stop a policy lapsing."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from src.repository.models import PremiumPayment
from tests.renewal_helpers import (
    IN_WINDOW,
    PREMIUM,
    count,
    issue_policy,
    pay,
    run_end_of_day,
    status_of,
)

pytestmark = pytest.mark.ac("AC-17")

_CUSTOMER = {"X-Actor-Id": "cust-001", "X-Actor-Role": "CUSTOMER"}
_ADMIN = {"X-Actor-Id": "admin-001", "X-Actor-Role": "ADMIN"}


def test_ac17_payment_recorded_append_only(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The payment row carries due date, exact Decimal amount, rule version and actor."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    before = count(seeded_engine, PremiumPayment)
    response = pay(api_client, number)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["amount"] == PREMIUM
    assert body["due_date"] == "2027-03-01"
    assert body["rule_version"] == 1
    assert body["actor_id"] == "cust-001"
    assert count(seeded_engine, PremiumPayment) == before + 1
    with Session(seeded_engine) as session:
        row = session.execute(
            select(PremiumPayment).where(PremiumPayment.id == body["payment_id"])
        ).scalar_one()
        assert row.amount == Decimal("15500.00")
        assert isinstance(row.amount, Decimal)


def test_ac17_paid_policy_does_not_lapse(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the grace end a paid policy is renewed, an unpaid sibling is lapsed."""
    paid = issue_policy(api_client, monkeypatch)
    unpaid = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    assert pay(api_client, paid).status_code == 201
    result = run_end_of_day(api_client, "2027-04-01")
    assert result.status_code == 200, result.text
    assert status_of(seeded_engine, paid) == "RENEWED"
    assert status_of(seeded_engine, unpaid) == "LAPSED"


def test_ac17_duplicate_payment_conflicts(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second payment for the same due date is 409 PREMIUM_ALREADY_PAID and writes nothing."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    assert pay(api_client, number).status_code == 201
    before = count(seeded_engine, PremiumPayment)
    duplicate = pay(api_client, number)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PREMIUM_ALREADY_PAID"
    assert count(seeded_engine, PremiumPayment) == before


def test_ac17_amount_mismatch_and_invalid_amounts(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wrong / non-positive / over-precise amounts are 422 and nothing is stored."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    before = count(seeded_engine, PremiumPayment)
    mismatch = pay(api_client, number, "10000.00")
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["details"] == [{"field": "amount", "code": "AMOUNT_MISMATCH"}]
    for bad in ("0.00", "-1.00", "100.005", "abc"):
        assert pay(api_client, number, bad).status_code == 422, bad
    as_number = api_client.post(
        f"/api/policies/{number}/payments", json={"amount": 15500}, headers=_CUSTOMER
    )
    assert as_number.status_code == 422
    assert as_number.json()["error"]["details"] == [
        {"field": "amount", "code": "MONEY_MUST_BE_STRING"}
    ]
    assert count(seeded_engine, PremiumPayment) == before


def test_ac17_payment_outside_window_and_owner_only(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before the window opens 409; another customer 404; an admin 403."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "2026-12-01")
    early = pay(api_client, number)
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "OUTSIDE_RENEWAL_WINDOW"
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    assert pay(api_client, number, actor_id="cust-002").status_code == 404
    admin = api_client.post(
        f"/api/policies/{number}/payments", json={"amount": PREMIUM}, headers=_ADMIN
    )
    assert admin.status_code == 403
