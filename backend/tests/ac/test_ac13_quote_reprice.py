"""AC-13: a quote reprices on its recorded rule version, never the current one."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.types.enums import ActorRole, ProductCode
from tests.conftest import actor_headers
from tests.quote_helpers import motor_request, publish_version


@pytest.mark.ac("AC-13")
def test_ac13_reprice_uses_recorded_version_after_new_publish(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-13: after MOTOR v2 (0.0320) is published the v1 quote still reprices to 14322.00."""
    headers = actor_headers(ActorRole.CUSTOMER)
    old = api_client.post("/api/quotes", json=motor_request(), headers=headers).json()
    publish_version(seeded_engine, ProductCode.MOTOR, 2, "0.0320")

    repriced = api_client.get(f"/api/quotes/{old['quote_id']}/reprice", headers=headers)
    assert repriced.status_code == 200, repriced.text
    assert repriced.json() == {
        "quote_id": old["quote_id"],
        "rule_version": 1,
        "stored_premium": "14322.00",
        "recomputed_premium": "14322.00",
        "matches": True,
    }

    fresh = api_client.post("/api/quotes", json=motor_request(), headers=headers).json()
    assert fresh["rule_version"] == 2
    assert fresh["premium"] == "14784.00"


@pytest.mark.ac("AC-13")
def test_ac13_reprice_is_owner_scoped(api_client: TestClient) -> None:
    """AC-13: another customer gets 404 on reprice; an underwriter may reprice."""
    created = api_client.post(
        "/api/quotes", json=motor_request(), headers=actor_headers(ActorRole.CUSTOMER)
    ).json()
    path = f"/api/quotes/{created['quote_id']}/reprice"
    other = api_client.get(path, headers=actor_headers(ActorRole.CUSTOMER, "cust-002"))
    assert other.status_code == 404
    assert api_client.get(path, headers=actor_headers(ActorRole.UNDERWRITER)).status_code == 200
