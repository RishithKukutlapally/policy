"""AC-08: cancelling appends an immutable pro-rata refund and moves the policy to CANCELLED."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.repository.models import AuditRecord, Refund
from src.repository.policy_lifecycle_repository import RefundRepository
from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.renewal_helpers import IN_WINDOW, audit_rows, cancel, count, issue_policy, pay, status_of

pytestmark = pytest.mark.ac("AC-08")

_CENT = Decimal("0.01")


def test_ac08_pro_rata_refund_matches_domain_calculation(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancel on 2026-06-01: 273 of 365 days unused -> 15500.00 x 273 / 365 - 250.00."""
    number = issue_policy(api_client, monkeypatch)
    expected = (Decimal("15500.00") * Decimal(273) / Decimal(365) - Decimal("250.00")).quantize(
        _CENT, ROUND_HALF_UP
    )
    assert expected == Decimal("11343.15")
    response = cancel(api_client, number, "2026-06-01")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "CANCELLED"
    refund = body["refund"]
    assert refund["amount"] == "11343.15"
    assert refund["refund_type"] == "PRO_RATA"
    assert refund["admin_fee"] == "250.00"
    assert refund["premium_paid"] == "15500.00"
    assert (refund["term_days"], refund["days_elapsed"], refund["unused_days"]) == (365, 92, 273)
    assert refund["reason"] == "Vehicle sold"
    assert refund["actor_id"] == "cust-001"
    assert status_of(seeded_engine, number) == "CANCELLED"


def test_ac08_refund_row_append_only_and_transition_written(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One Decimal refund row, one ACTIVE -> CANCELLED transition, no mutating repository API."""
    number = issue_policy(api_client, monkeypatch)
    assert cancel(api_client, number, "2026-06-01").status_code == 200
    with Session(seeded_engine) as session:
        refunds = list(session.query(Refund).all())
        assert len(refunds) == 1
        assert refunds[0].amount == Decimal("11343.15")
        assert isinstance(refunds[0].amount, Decimal)
    assert not [n for n in dir(RefundRepository) if "update" in n or "delete" in n]
    detail = api_client.get(
        f"/api/policies/{number}", headers=actor_headers(ActorRole.CUSTOMER)
    ).json()
    assert detail["status"] == "CANCELLED"
    assert [(t["from_status"], t["to_status"]) for t in detail["transitions"]][-1] == (
        "ACTIVE",
        "CANCELLED",
    )
    assert len(detail["refunds"]) == 1


def test_ac08_cancel_twice_is_409_and_writes_no_second_refund(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second cancel is INVALID_POLICY_STATE and the refund count stays at one."""
    number = issue_policy(api_client, monkeypatch)
    assert cancel(api_client, number, "2026-06-01").status_code == 200
    second = cancel(api_client, number, "2026-06-02")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "INVALID_POLICY_STATE"
    assert second.json()["error"]["details"] == {"current": "CANCELLED", "target": "CANCELLED"}
    assert count(seeded_engine, Refund) == 1


def test_ac08_date_outside_term_is_422(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A date after expiry (or before the start) is VALIDATION_ERROR / OUTSIDE_TERM."""
    number = issue_policy(api_client, monkeypatch)
    for bad in ("2027-03-01", "2026-02-28"):
        response = cancel(api_client, number, bad)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert response.json()["error"]["details"] == [
            {"field": "cancellation_date", "code": "OUTSIDE_TERM"}
        ]
    assert count(seeded_engine, Refund) == 0
    assert status_of(seeded_engine, number) == "ACTIVE"


def test_ac08_reason_and_access_rules(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reason is required and <= 200 chars; other customers 404; underwriters 403; no auth 401."""
    number = issue_policy(api_client, monkeypatch)
    assert cancel(api_client, number, "2026-06-01", reason="").status_code == 422
    assert cancel(api_client, number, "2026-06-01", reason="x" * 201).status_code == 422
    assert cancel(api_client, number, "2026-06-01", actor_id="cust-002").status_code == 404
    assert cancel(api_client, number, "2026-06-01", role=ActorRole.UNDERWRITER).status_code == 403
    unauth = api_client.post(
        f"/api/policies/{number}/cancel",
        json={"cancellation_date": "2026-06-01", "reason": "x"},
    )
    assert unauth.status_code == 401


def test_ac08_only_admin_cancellation_is_audited(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Customer cancellation writes no audit row; an admin cancellation writes POLICY_CANCELLED."""
    mine = issue_policy(api_client, monkeypatch)
    theirs = issue_policy(api_client, monkeypatch)
    assert cancel(api_client, mine, "2026-06-01").status_code == 200
    assert audit_rows(seeded_engine, "POLICY_CANCELLED") == []
    assert cancel(api_client, theirs, "2026-06-01", role=ActorRole.ADMIN).status_code == 200
    rows: list[AuditRecord] = audit_rows(seeded_engine, "POLICY_CANCELLED")
    assert [(r.actor_id, r.entity_id) for r in rows] == [("admin-001", theirs)]


def test_ac08_renewal_term_gets_no_free_look(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renewal successor cancelled on day 5 is pro-rata (base = the renewal payment)."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    assert pay(api_client, number).status_code == 201
    headers = actor_headers(ActorRole.CUSTOMER)
    successor = api_client.post(f"/api/policies/{number}/renew", headers=headers).json()
    # term 2027-03-01..2028-02-29 = 366 days; cancelled 2027-03-06 -> 5 elapsed, 361 unused
    expected = (Decimal("15500.00") * Decimal(361) / Decimal(366) - Decimal("250.00")).quantize(
        _CENT, ROUND_HALF_UP
    )
    assert expected == Decimal("15038.25")
    response = cancel(api_client, successor["policy_number"], "2027-03-06")
    assert response.status_code == 200, response.text
    refund = response.json()["refund"]
    assert refund["refund_type"] == "PRO_RATA"
    assert refund["amount"] == "15038.25"
    assert refund["term_days"] == 366
