"""AC-14: underwriter queue, approve/decline, audited with the actor id."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository.models import AuditRecord, UnderwritingDecision
from src.types.enums import ActorRole
from tests.application_helpers import audit_rows, motor_application
from tests.conftest import actor_headers

UW = actor_headers(ActorRole.UNDERWRITER)
APPROVE = {"decision": "APPROVE", "reason_codes": ["MO-UW-900"], "comment": "Vehicle inspected"}


def _decision_url(application_id: str) -> str:
    return f"/api/underwriting/applications/{application_id}/decision"


@pytest.mark.ac("AC-14")
def test_ac14_queue_lists_only_manual_review_oldest_first(api_client: TestClient) -> None:
    """AC-14: queue holds the two MANUAL_REVIEW cases in creation order, no raw PII."""
    motor_application(api_client, 3)
    first = motor_application(api_client, 12)
    motor_application(api_client, 16)
    second = motor_application(api_client, 11)
    response = api_client.get("/api/underwriting/queue", headers=UW)
    assert response.status_code == 200
    assert [item["application_id"] for item in response.json()] == [first, second]
    item = response.json()[0]
    assert item["product"] == "MOTOR"
    assert item["reason_codes"] == ["MO-UW-002"]
    assert item["rule_version"] == 1
    assert "999900000001" not in response.text
    assert "AAAAA0001A" not in response.text


@pytest.mark.ac("AC-14")
def test_ac14_approve_appends_decision_and_audit_row(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-14: APPROVE -> AUTO_BIND, second decision row by uw-001, one UW_APPROVE audit row."""
    app_id = motor_application(api_client, 12)
    headers = {**UW, "X-Correlation-ID": "corr-uw-1"}
    response = api_client.post(_decision_url(app_id), json=APPROVE, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "AUTO_BIND"
    with Session(seeded_engine) as session:
        rows = list(
            session.execute(
                select(UnderwritingDecision).where(UnderwritingDecision.application_id == app_id)
            ).scalars()
        )
    assert sorted(r.decided_by for r in rows) == ["SYSTEM", "uw-001"]
    system = next(r for r in rows if r.decided_by == "SYSTEM")
    assert system.decision == "MANUAL_REVIEW"
    uw_row = next(r for r in rows if r.decided_by == "uw-001")
    assert (uw_row.decision, uw_row.reason_codes) == ("AUTO_BIND", ["MO-UW-900"])
    audits = audit_rows(seeded_engine, app_id)
    assert len(audits) == 1
    audit = audits[0]
    assert (audit.action, audit.actor_id) == ("UW_APPROVE", "uw-001")
    assert audit.actor_role == "UNDERWRITER"
    assert audit.entity_type == "APPLICATION"
    assert audit.correlation_id == "corr-uw-1"


@pytest.mark.ac("AC-14")
def test_ac14_decline_sets_declined_status(api_client: TestClient, seeded_engine: Engine) -> None:
    """AC-14: DECLINE with MO-UW-902 -> DECLINED and a UW_DECLINE audit row."""
    app_id = motor_application(api_client, 12)
    body = {"decision": "DECLINE", "reason_codes": ["MO-UW-902"]}
    response = api_client.post(_decision_url(app_id), json=body, headers=UW)
    assert response.status_code == 200
    assert response.json()["status"] == "DECLINED"
    assert audit_rows(seeded_engine, app_id)[0].action == "UW_DECLINE"


@pytest.mark.ac("AC-14")
def test_ac14_missing_or_unknown_reason_codes_rejected(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-14: [] -> 422 REQUIRED; TL-UW-001 on MOTOR -> 422 UNKNOWN_REASON_CODE; nothing written."""
    app_id = motor_application(api_client, 12)
    empty = api_client.post(
        _decision_url(app_id), json={"decision": "APPROVE", "reason_codes": []}, headers=UW
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"
    unknown = api_client.post(
        _decision_url(app_id),
        json={"decision": "APPROVE", "reason_codes": ["TL-UW-001"]},
        headers=UW,
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["details"][0]["code"] == "UNKNOWN_REASON_CODE"
    assert audit_rows(seeded_engine, app_id) == []
    with Session(seeded_engine) as session:
        assert session.execute(select(func.count()).select_from(AuditRecord)).scalar_one() == 0


@pytest.mark.ac("AC-14")
def test_ac14_deciding_a_non_manual_review_case_conflicts(api_client: TestClient) -> None:
    """AC-14: AUTO_BIND application -> 409 INVALID_APPLICATION_STATE; unknown id -> 404."""
    app_id = motor_application(api_client, 3)
    response = api_client.post(_decision_url(app_id), json=APPROVE, headers=UW)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_APPLICATION_STATE"
    missing = api_client.post(
        _decision_url("00000000-0000-4000-8000-000000000000"), json=APPROVE, headers=UW
    )
    assert missing.status_code == 404


@pytest.mark.ac("AC-14")
def test_ac14_roles_are_enforced(api_client: TestClient) -> None:
    """AC-14: 401 without headers, 403 for CUSTOMER; ADMIN reads the queue but cannot decide."""
    app_id = motor_application(api_client, 12)
    assert api_client.get("/api/underwriting/queue").status_code == 401
    assert api_client.post(_decision_url(app_id), json=APPROVE).status_code == 401
    customer = actor_headers(ActorRole.CUSTOMER)
    assert api_client.get("/api/underwriting/queue", headers=customer).status_code == 403
    assert api_client.post(_decision_url(app_id), json=APPROVE, headers=customer).status_code == 403
    admin = actor_headers(ActorRole.ADMIN)
    assert api_client.get("/api/underwriting/queue", headers=admin).status_code == 200
    assert api_client.post(_decision_url(app_id), json=APPROVE, headers=admin).status_code == 403


@pytest.mark.ac("AC-14")
def test_ac14_underwriter_cannot_override(api_client: TestClient) -> None:
    """AC-14: UNDERWRITER override attempt -> 403."""
    app_id = motor_application(api_client, 16)
    response = api_client.post(
        f"/api/underwriting/applications/{app_id}/override",
        json={"reason_code": "MO-UW-901", "comment": "Vehicle restored and certified"},
        headers=UW,
    )
    assert response.status_code == 403


@pytest.mark.ac("AC-14")
def test_ac14_audit_trail_lists_decisions_and_audit_rows(api_client: TestClient) -> None:
    """AC-14: GET .../audit returns decisions and audit records oldest first."""
    app_id = motor_application(api_client, 12)
    api_client.post(_decision_url(app_id), json=APPROVE, headers=UW)
    url = f"/api/underwriting/applications/{app_id}/audit"
    response = api_client.get(url, headers=UW)
    assert response.status_code == 200
    body = response.json()
    assert [d["decided_by"] for d in body["decisions"]] == ["SYSTEM", "uw-001"]
    assert [a["action"] for a in body["audit_records"]] == ["UW_APPROVE"]
    customer = actor_headers(ActorRole.CUSTOMER)
    assert api_client.get(url, headers=customer).status_code == 403
