"""AC-04 over HTTP: automatic decision with reason codes from the active rule version."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from src.repository.models import UnderwritingDecision
from tests.application_helpers import TERM_LIFE_INPUTS, application_for, create_quote, submit


@pytest.mark.ac("AC-04")
def test_ac04_motor_clean_returns_auto_bind(api_client: TestClient) -> None:
    """AC-04: a clean MOTOR risk -> AUTO_BIND with no reason codes."""
    body = application_for(api_client, "MOTOR")
    assert (body["status"], body["decision"]) == ("AUTO_BIND", "AUTO_BIND")
    assert body["reason_codes"] == []


@pytest.mark.ac("AC-04")
def test_ac04_motor_old_vehicle_returns_manual_review(api_client: TestClient) -> None:
    """AC-04: vehicle 12 years old -> MANUAL_REVIEW with MO-UW-002."""
    body = application_for(api_client, "MOTOR", vehicle_age_years=12)
    assert body["status"] == "MANUAL_REVIEW"
    assert body["decision"] == "MANUAL_REVIEW"
    assert body["reason_codes"] == ["MO-UW-002"]
    assert body["reasons"] == [{"code": "MO-UW-002", "description": "Vehicle older than 10 years"}]


@pytest.mark.ac("AC-04")
def test_ac04_motor_very_old_vehicle_returns_decline(api_client: TestClient) -> None:
    """AC-04: vehicle 16 years old -> DECLINE (status DECLINED) with MO-UW-001 and MO-UW-002."""
    body = application_for(api_client, "MOTOR", vehicle_age_years=16)
    assert body["status"] == "DECLINED"
    assert body["decision"] == "DECLINE"
    assert body["reason_codes"] == ["MO-UW-001", "MO-UW-002"]


@pytest.mark.ac("AC-04")
def test_ac04_term_life_age_at_term_end_returns_decline(api_client: TestClient) -> None:
    """AC-04: age 60 + term 20 -> DECLINE TL-UW-001."""
    body = application_for(api_client, "TERM_LIFE", age=60)
    assert body["decision"] == "DECLINE"
    assert body["reason_codes"] == ["TL-UW-001"]


@pytest.mark.ac("AC-04")
def test_ac04_household_thatch_returns_decline(api_client: TestClient) -> None:
    """AC-04: THATCH construction -> DECLINE HH-UW-001."""
    body = application_for(api_client, "HOUSEHOLD", construction_type="THATCH")
    assert body["status"] == "DECLINED"
    assert body["reason_codes"] == ["HH-UW-001"]


@pytest.mark.ac("AC-04")
def test_ac04_household_flood_zone_high_value_returns_manual_review(
    api_client: TestClient,
) -> None:
    """AC-04: flood zone above 5,000,000 -> MANUAL_REVIEW HH-UW-002."""
    body = application_for(api_client, "HOUSEHOLD", in_flood_zone=True, sum_insured="6000000.00")
    assert body["decision"] == "MANUAL_REVIEW"
    assert body["reason_codes"] == ["HH-UW-002"]


@pytest.mark.ac("AC-04")
def test_ac04_term_life_pre_existing_condition_returns_manual_review(
    api_client: TestClient,
) -> None:
    """AC-04: TERM_LIFE with a declared condition -> MANUAL_REVIEW TL-UW-003."""
    quote_id = create_quote(api_client, {"product": "TERM_LIFE", "inputs": TERM_LIFE_INPUTS})
    response = submit(api_client, quote_id, health={"has_pre_existing_condition": True})
    body: dict[str, Any] = response.json()
    assert response.status_code == 201, response.text
    assert body["reason_codes"] == ["TL-UW-003"]
    assert "has_pre_existing_condition" not in response.text


@pytest.mark.ac("AC-04")
def test_ac04_decision_records_rule_version(api_client: TestClient, seeded_engine: Engine) -> None:
    """AC-04: the stored SYSTEM decision carries the rule version and sorted codes."""
    body = application_for(api_client, "MOTOR", vehicle_age_years=16)
    with Session(seeded_engine) as session:
        row = session.execute(
            select(UnderwritingDecision).where(
                UnderwritingDecision.application_id == body["application_id"]
            )
        ).scalar_one()
        assert row.rule_version == 1
        assert row.decided_by == "SYSTEM"
        assert row.decision == "DECLINE"
        assert row.reason_codes == ["MO-UW-001", "MO-UW-002"]
