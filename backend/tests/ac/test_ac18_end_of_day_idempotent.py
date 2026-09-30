"""AC-18: the end-of-day run is idempotent and skips (and reports) a failing policy."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from src.service.renewal_service import RenewalService

from src.types.enums import ActorRole
from tests.conftest import actor_headers
from tests.renewal_helpers import (
    IN_WINDOW,
    audit_rows,
    counts,
    issue_policy,
    pay,
    run_end_of_day,
    status_of,
)

pytestmark = pytest.mark.ac("AC-18")


@pytest.fixture(name="portfolio")
def _portfolio(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[str], list[str]]:
    """Two paid (renewable) and one unpaid (lapsing) policy, all due 2027-03-01."""
    paid = [issue_policy(api_client, monkeypatch) for _ in range(2)]
    unpaid = [issue_policy(api_client, monkeypatch)]
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    for number in paid:
        assert pay(api_client, number).status_code == 201
    return paid, unpaid


def test_ac18_first_run_then_rerun_changes_nothing(
    api_client: TestClient, seeded_engine: Engine, portfolio: tuple[list[str], list[str]]
) -> None:
    """Run 1 renews 2 and lapses 1; the identical re-run returns zeros and adds no rows."""
    paid, unpaid = portfolio
    first = run_end_of_day(api_client, "2027-04-01")
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["renewed"], body["lapsed"], body["failed"]) == (2, 1, 0)
    assert sorted(item["from"] for item in body["renewed_policies"]) == sorted(paid)
    assert body["lapsed_policies"] == unpaid
    after_first = counts(seeded_engine)
    assert after_first["policies"] == 3 + 2
    second = run_end_of_day(api_client, "2027-04-01")
    assert second.status_code == 200
    again = second.json()
    assert (again["renewed"], again["lapsed"], again["failed"]) == (0, 0, 0)
    assert counts(seeded_engine) == after_first
    assert all(status_of(seeded_engine, n) == "RENEWED" for n in paid)
    assert status_of(seeded_engine, unpaid[0]) == "LAPSED"


def test_ac18_each_run_is_audited_with_actor(
    api_client: TestClient, seeded_engine: Engine, portfolio: tuple[list[str], list[str]]
) -> None:
    """One RUN_END_OF_DAY audit row per run carrying actor id, as_of and the counts."""
    run_end_of_day(api_client, "2027-04-01")
    rows = audit_rows(seeded_engine, "RUN_END_OF_DAY")
    assert len(rows) == 1
    assert rows[0].actor_id == "admin-001"
    assert rows[0].entity_id == "2027-04-01"
    assert rows[0].detail is not None
    assert rows[0].detail["renewed"] == 2
    assert rows[0].detail["lapsed"] == 1
    run_end_of_day(api_client, "2027-04-01")
    assert len(audit_rows(seeded_engine, "RUN_END_OF_DAY")) == 2


def test_ac18_failing_policy_is_skipped_and_reported(
    api_client: TestClient,
    seeded_engine: Engine,
    portfolio: tuple[list[str], list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One policy raising rolls back only itself; a later re-run completes it exactly once."""
    paid, _ = portfolio
    poisoned = paid[0]
    original = RenewalService.apply_renewal

    def flaky(self: RenewalService, policy_number: str, *args: Any, **kwargs: Any) -> Any:
        if policy_number == poisoned:
            raise RuntimeError("boom")
        return original(self, policy_number, *args, **kwargs)

    monkeypatch.setattr(RenewalService, "apply_renewal", flaky)
    body = run_end_of_day(api_client, "2027-04-01").json()
    assert (body["renewed"], body["lapsed"], body["failed"]) == (1, 1, 1)
    assert body["failed_policies"][0]["policy_number"] == poisoned
    assert status_of(seeded_engine, poisoned) == "ACTIVE"
    monkeypatch.setattr(RenewalService, "apply_renewal", original)
    retry = run_end_of_day(api_client, "2027-04-01").json()
    assert (retry["renewed"], retry["lapsed"], retry["failed"]) == (1, 0, 0)
    assert status_of(seeded_engine, poisoned) == "RENEWED"


def test_ac18_end_of_day_requires_admin(api_client: TestClient) -> None:
    """401 without headers, 403 for CUSTOMER and UNDERWRITER."""
    assert api_client.post("/api/admin/end-of-day", json={"as_of": "2027-04-01"}).status_code == 401
    for role in (ActorRole.CUSTOMER, ActorRole.UNDERWRITER):
        response = api_client.post(
            "/api/admin/end-of-day", json={"as_of": "2027-04-01"}, headers=actor_headers(role)
        )
        assert response.status_code == 403
    bad = api_client.post(
        "/api/admin/end-of-day", json={"as_of": "nope"}, headers=actor_headers(ActorRole.ADMIN)
    )
    assert bad.status_code == 422
