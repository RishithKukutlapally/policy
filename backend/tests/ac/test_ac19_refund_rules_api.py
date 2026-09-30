"""AC-19: free look refunds the full premium with no fee; the preview persists nothing."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.repository.models import PolicyStateTransition, Refund
from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.renewal_helpers import cancel, count, issue_policy, status_of

pytestmark = pytest.mark.ac("AC-19")


def _preview(client: TestClient, number: str, date: str | None) -> httpx.Response:
    params = {} if date is None else {"date": date}
    return client.get(
        f"/api/policies/{number}/cancellation-preview",
        params=params,
        headers=actor_headers(ActorRole.CUSTOMER),
    )


def test_ac19_free_look_preview_refunds_full_premium(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Day 9 of the term is inside the 15-day free look: 15500.00, no fee, nothing written."""
    number = issue_policy(api_client, monkeypatch)
    before = (count(seeded_engine, Refund), count(seeded_engine, PolicyStateTransition))
    response = _preview(api_client, number, "2026-03-10")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["refund_type"] == "FREE_LOOK"
    assert body["amount"] == "15500.00"
    assert body["admin_fee"] == "0.00"
    assert body["premium_paid"] == "15500.00"
    assert body["gross_refund"] == "15500.00"
    assert (count(seeded_engine, Refund), count(seeded_engine, PolicyStateTransition)) == before
    assert status_of(seeded_engine, number) == "ACTIVE"


def test_ac19_pro_rata_preview_breakdown(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Day 92: gross 11593.15 less the 250.00 fee = 11343.15; 16 days elapsed is past free look."""
    number = issue_policy(api_client, monkeypatch)
    body = _preview(api_client, number, "2026-06-01").json()
    assert body["refund_type"] == "PRO_RATA"
    assert body["gross_refund"] == "11593.15"
    assert body["admin_fee"] == "250.00"
    assert body["amount"] == "11343.15"
    assert (body["term_days"], body["days_elapsed"], body["unused_days"]) == (365, 92, 273)
    last_free_look = _preview(api_client, number, "2026-03-16").json()
    assert last_free_look["refund_type"] == "FREE_LOOK"
    first_pro_rata = _preview(api_client, number, "2026-03-17").json()
    assert first_pro_rata["refund_type"] == "PRO_RATA"
    assert count(seeded_engine, Refund) == 0


def test_ac19_preview_matches_cancel_and_free_look_cancel_has_no_fee(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The persisted free-look refund equals the preview."""
    number = issue_policy(api_client, monkeypatch)
    preview = _preview(api_client, number, "2026-03-10").json()
    response = cancel(api_client, number, "2026-03-10")
    assert response.status_code == 200, response.text
    refund = response.json()["refund"]
    assert refund["amount"] == preview["amount"] == "15500.00"
    assert refund["refund_type"] == "FREE_LOOK"
    assert refund["admin_fee"] == "0.00"
    assert count(seeded_engine, Refund) == 1


def test_ac19_preview_errors(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing or malformed date 422; outside the term 422 OUTSIDE_TERM; foreign policy 404."""
    number = issue_policy(api_client, monkeypatch)
    assert _preview(api_client, number, None).status_code == 422
    assert _preview(api_client, number, "01/06/2026").status_code == 422
    assert _preview(api_client, number, "2027-01-01").status_code == 200  # inside the term
    beyond = _preview(api_client, number, "2027-03-01")
    assert beyond.status_code == 422
    assert beyond.json()["error"]["details"] == [
        {"field": "cancellation_date", "code": "OUTSIDE_TERM"}
    ]
    other = api_client.get(
        f"/api/policies/{number}/cancellation-preview",
        params={"date": "2026-06-01"},
        headers=actor_headers(ActorRole.CUSTOMER, "cust-002"),
    )
    assert other.status_code == 404


def test_ac19_preview_and_cancel_expose_the_domain_breakdown(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every money field is a 2 dp string and net == gross - fee; cancel persists the preview."""
    from decimal import Decimal

    number = issue_policy(api_client, monkeypatch)
    preview = _preview(api_client, number, "2026-06-01").json()
    for key in ("premium_paid", "gross_refund", "admin_fee", "amount"):
        assert len(preview[key].split(".")[1]) == 2
    assert Decimal(preview["amount"]) == Decimal(preview["gross_refund"]) - Decimal(
        preview["admin_fee"]
    )
    refund = cancel(api_client, number, "2026-06-01").json()["refund"]
    assert (refund["amount"], refund["admin_fee"]) == (preview["amount"], preview["admin_fee"])
    assert refund["refund_type"] == preview["refund_type"] == "PRO_RATA"
