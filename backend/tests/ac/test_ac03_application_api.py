"""AC-03 over HTTP: application capture, KYC stub validation and masked storage."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository.models import Application, UnderwritingDecision
from src.types.enums import ActorRole, ProductCode
from tests.application_helpers import KYC, TERM_LIFE_INPUTS, create_quote, submit
from tests.conftest import actor_headers
from tests.quote_helpers import motor_request, publish_version


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())


@pytest.mark.ac("AC-03")
def test_ac03_valid_application_moves_to_underwriting(api_client: TestClient) -> None:
    """AC-03: valid golden MOTOR application -> 201, decided, status history via UNDERWRITING."""
    quote_id = create_quote(api_client, motor_request())
    response = submit(api_client, quote_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "AUTO_BIND"
    assert body["decision"] == "AUTO_BIND"
    assert body["reason_codes"] == []
    assert body["rule_version"] == 1
    assert body["status_history"] == ["SUBMITTED", "UNDERWRITING", "AUTO_BIND"]
    assert body["kyc"]["aadhaar_masked"] == "XXXX-XXXX-0001"
    assert body["kyc"]["pan_masked"] == "XXXXX0001X"
    fetched = api_client.get(
        f"/api/applications/{body['application_id']}",
        headers=actor_headers(ActorRole.CUSTOMER),
    )
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "AUTO_BIND"
    assert len(fetched.json()["decisions"]) == 1
    assert fetched.json()["decisions"][0]["decided_by"] == "SYSTEM"


@pytest.mark.ac("AC-03")
def test_ac03_invalid_kyc_rejected_and_nothing_persisted(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-03: bad PAN and Aadhaar -> 422 listing every field; no rows written."""
    quote_id = create_quote(api_client, motor_request())
    response = submit(api_client, quote_id, kyc={**KYC, "pan": "ABC123", "aadhaar": "123"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {"field": "kyc.pan", "code": "INVALID_FORMAT"} in error["details"]
    assert {"field": "kyc.aadhaar", "code": "INVALID_FORMAT"} in error["details"]
    assert "ABC123" not in response.text
    assert _count(seeded_engine, Application) == 0
    assert _count(seeded_engine, UnderwritingDecision) == 0


@pytest.mark.ac("AC-03")
def test_ac03_unknown_or_foreign_quote_is_404(api_client: TestClient) -> None:
    """AC-03: unknown quote id and another customer's quote both answer 404 NOT_FOUND."""
    missing = submit(api_client, "00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    quote_id = create_quote(api_client, motor_request())
    foreign = submit(api_client, quote_id, actor_id="cust-002")
    assert foreign.status_code == 404


@pytest.mark.ac("AC-03")
def test_ac03_only_masked_kyc_is_stored(api_client: TestClient, seeded_engine: Engine) -> None:
    """AC-03: the stored row keeps masked Aadhaar/PAN only; raw values appear nowhere."""
    response = submit(api_client, create_quote(api_client, motor_request()))
    assert response.status_code == 201
    assert "999900000001" not in response.text
    assert "AAAAA0001A" not in response.text
    with Session(seeded_engine) as session:
        row = session.execute(select(Application)).scalar_one()
        assert row.aadhaar_masked == "XXXX-XXXX-0001"
        assert row.pan_masked == "XXXXX0001X"
        dump = " ".join(str(getattr(row, c.name)) for c in Application.__table__.columns)
    assert "999900000001" not in dump
    assert "AAAAA0001A" not in dump


@pytest.mark.ac("AC-03")
def test_ac03_health_declaration_required_for_term_life_only(api_client: TestClient) -> None:
    """AC-03: TERM_LIFE needs a health declaration (REQUIRED); MOTOR rejects one (UNKNOWN_FIELD)."""
    tl_quote = create_quote(api_client, {"product": "TERM_LIFE", "inputs": TERM_LIFE_INPUTS})
    missing = submit(api_client, tl_quote)
    assert missing.status_code == 422
    assert {"field": "health_declaration", "code": "REQUIRED"} in missing.json()["error"]["details"]
    extra = submit(
        api_client,
        create_quote(api_client, motor_request()),
        health={"has_pre_existing_condition": False},
    )
    assert extra.status_code == 422
    details = extra.json()["error"]["details"]
    assert {"field": "health_declaration", "code": "UNKNOWN_FIELD"} in details


@pytest.mark.ac("AC-03")
def test_ac03_stale_quote_conflicts(api_client: TestClient, seeded_engine: Engine) -> None:
    """AC-03: a quote priced on a superseded version -> 409 QUOTE_STALE."""
    quote_id = create_quote(api_client, motor_request())
    publish_version(seeded_engine, ProductCode.MOTOR, 2, "0.0400")
    response = submit(api_client, quote_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "QUOTE_STALE"


@pytest.mark.ac("AC-03")
def test_ac03_application_endpoints_are_role_guarded(api_client: TestClient) -> None:
    """AC-03: no headers -> 401; UNDERWRITER/ADMIN cannot submit -> 403; owner-only GET."""
    quote_id = create_quote(api_client, motor_request())
    body = {"quote_id": quote_id, "kyc": KYC}
    assert api_client.post("/api/applications", json=body).status_code == 401
    for role in (ActorRole.UNDERWRITER, ActorRole.ADMIN):
        response = api_client.post("/api/applications", json=body, headers=actor_headers(role))
        assert response.status_code == 403
    app_id = submit(api_client, quote_id).json()["application_id"]
    other = api_client.get(
        f"/api/applications/{app_id}", headers=actor_headers(ActorRole.CUSTOMER, "cust-002")
    )
    assert other.status_code == 404
    staff = api_client.get(
        f"/api/applications/{app_id}", headers=actor_headers(ActorRole.UNDERWRITER)
    )
    assert staff.status_code == 200
