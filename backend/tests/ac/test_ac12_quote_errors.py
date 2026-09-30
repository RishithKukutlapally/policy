"""AC-12: quote refusals persist nothing and use the canonical error envelope."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository.models import Quote
from src.types.enums import ActorRole, ProductCode
from tests.conftest import actor_headers
from tests.quote_helpers import drop_product_versions, motor_request, publish_version


def _quote_count(engine: Engine) -> int:
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(Quote)).scalar() or 0)


@pytest.mark.ac("AC-12")
def test_ac12_sum_insured_below_minimum_is_422_and_persists_nothing(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-12: MOTOR sum insured 50000.00 -> 422 VALIDATION_ERROR on sum_insured, no row."""
    response = api_client.post(
        "/api/quotes",
        json=motor_request(sum_insured="50000.00"),
        headers=actor_headers(ActorRole.CUSTOMER),
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {"field": "sum_insured", "code": "OUT_OF_RANGE"} in error["details"]
    assert _quote_count(seeded_engine) == 0


@pytest.mark.ac("AC-12")
def test_ac12_every_failing_field_is_reported(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-12: all failures at once, including a missing field and an unknown field."""
    body = motor_request(owner_age=10, zone="Z")
    del body["inputs"]["engine_cc"]
    body["inputs"]["colour"] = "red"
    response = api_client.post("/api/quotes", json=body, headers=actor_headers(ActorRole.CUSTOMER))
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert {"field": "owner_age", "code": "OUT_OF_RANGE"} in details
    assert {"field": "engine_cc", "code": "REQUIRED"} in details
    assert {"field": "zone", "code": "INVALID_FORMAT"} in details
    assert {"field": "colour", "code": "UNKNOWN_FIELD"} in details
    assert _quote_count(seeded_engine) == 0


@pytest.mark.ac("AC-12")
def test_ac12_money_as_json_number_is_rejected(api_client: TestClient) -> None:
    """AC-12: a JSON number for sum_insured -> MONEY_MUST_BE_STRING."""
    response = api_client.post(
        "/api/quotes",
        json=motor_request(sum_insured=500000),
        headers=actor_headers(ActorRole.CUSTOMER),
    )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert {"field": "sum_insured", "code": "MONEY_MUST_BE_STRING"} in details


@pytest.mark.ac("AC-12")
def test_ac12_unknown_product_is_404(api_client: TestClient) -> None:
    """AC-12: an unknown product code -> 404 NOT_FOUND."""
    response = api_client.post(
        "/api/quotes",
        json={"product": "PET", "inputs": {}},
        headers=actor_headers(ActorRole.CUSTOMER),
    )
    assert response.status_code == 404


@pytest.mark.ac("AC-12")
def test_ac12_draft_only_product_is_409_without_fallback(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-12: only a DRAFT exists -> 409 NO_PUBLISHED_VERSION, nothing persisted."""
    drop_product_versions(seeded_engine, ProductCode.MOTOR)
    publish_version(seeded_engine, ProductCode.MOTOR, 1, "0.0310", published=False)
    response = api_client.post(
        "/api/quotes", json=motor_request(), headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_PUBLISHED_VERSION"
    assert _quote_count(seeded_engine) == 0
