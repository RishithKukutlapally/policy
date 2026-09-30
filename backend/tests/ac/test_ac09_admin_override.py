"""AC-09: admin override of a DECLINED application, audited and append-only."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository.models import (
    Application,
    AuditRecord,
    UnderwritingDecision,
    UnderwritingOverride,
)
from src.types.enums import ActorRole
from tests.application_helpers import audit_rows, motor_application
from tests.conftest import actor_headers

ADMIN = actor_headers(ActorRole.ADMIN)
OVERRIDE = {"reason_code": "MO-UW-901", "comment": "Vehicle restored and certified roadworthy"}


def _url(application_id: str) -> str:
    return f"/api/underwriting/applications/{application_id}/override"


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())


@pytest.mark.ac("AC-09")
def test_ac09_admin_override_appends_decision_override_and_audit(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-09: override -> AUTO_BIND, new decision, override row, UW_OVERRIDE_DECLINE audit row."""
    app_id = motor_application(api_client, 16)
    with Session(seeded_engine) as session:
        original = session.execute(select(UnderwritingDecision)).scalar_one()
        snapshot = (original.id, original.decision, original.reason_codes, original.decided_by)
    response = api_client.post(_url(app_id), json=OVERRIDE, headers=ADMIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "AUTO_BIND"
    assert body["override"]["from_status"] == "DECLINED"
    assert body["override"]["to_status"] == "AUTO_BIND"
    assert body["override"]["actor_id"] == "admin-001"
    with Session(seeded_engine) as session:
        decisions = list(session.execute(select(UnderwritingDecision)).scalars())
        assert len(decisions) == 2
        first = next(d for d in decisions if d.id == snapshot[0])
        assert (first.id, first.decision, first.reason_codes, first.decided_by) == snapshot
        latest = next(d for d in decisions if d.id != snapshot[0])
        assert (latest.decision, latest.decided_by) == ("AUTO_BIND", "admin-001")
        override = session.execute(select(UnderwritingOverride)).scalar_one()
        assert override.original_decision_id == snapshot[0]
        assert (override.application_id, override.reason_code) == (app_id, "MO-UW-901")
        assert override.comment == OVERRIDE["comment"]
        assert override.actor_id == "admin-001"
        application = session.get(Application, app_id)
        assert application is not None and application.status == "AUTO_BIND"
    audits = audit_rows(seeded_engine, app_id)
    assert len(audits) == 1
    assert (audits[0].action, audits[0].actor_id) == ("UW_OVERRIDE_DECLINE", "admin-001")
    assert audits[0].actor_role == "ADMIN"
    assert audits[0].detail is not None
    assert audits[0].detail["comment"] == OVERRIDE["comment"]


@pytest.mark.ac("AC-09")
def test_ac09_override_comment_pii_is_masked_in_the_audit_row_and_api(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-09 / NFR-03: an Aadhaar or PAN typed into the comment is stored and returned masked."""
    app_id = motor_application(api_client, 16)
    comment = "Verified Aadhaar 999900000001 and PAN AAAAA0001A against the paper file"
    body = {"reason_code": "MO-UW-901", "comment": comment}
    assert api_client.post(_url(app_id), json=body, headers=ADMIN).status_code == 200
    audits = audit_rows(seeded_engine, app_id)
    assert len(audits) == 1
    stored = audits[0].detail
    assert stored is not None
    assert "999900000001" not in json.dumps(stored)
    assert "AAAAA0001A" not in json.dumps(stored)
    assert "XXXX-XXXX-0001" in stored["comment"]
    assert "XXXXX0001X" in stored["comment"]
    trail = api_client.get(f"/api/underwriting/applications/{app_id}/audit", headers=ADMIN)
    assert trail.status_code == 200
    records = trail.json()["audit_records"]
    assert any("XXXX-XXXX-0001" in json.dumps(r) for r in records)
    assert "999900000001" not in json.dumps(records)
    assert "AAAAA0001A" not in json.dumps(records)


@pytest.mark.ac("AC-09")
def test_ac09_decision_comment_pii_is_masked_in_the_audit_row(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-09 / NFR-03: the underwriter decision comment is sanitised on the same path."""
    app_id = motor_application(api_client, 12)
    decision = {
        "decision": "APPROVE",
        "reason_codes": ["MO-UW-900"],
        "comment": "PAN AAAAA0001A, aadhaar 9999-0000-0001 seen",
    }
    url = f"/api/underwriting/applications/{app_id}/decision"
    uw = actor_headers(ActorRole.UNDERWRITER)
    assert api_client.post(url, json=decision, headers=uw).status_code == 200
    stored = audit_rows(seeded_engine, app_id)[0].detail
    assert stored is not None
    dumped = json.dumps(stored)
    assert "AAAAA0001A" not in dumped
    assert "9999-0000-0001" not in dumped
    assert "999900000001" not in dumped
    assert "XXXXX0001X" in stored["comment"]


@pytest.mark.ac("AC-09")
def test_ac09_invalid_override_writes_nothing(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-09: short comment, unknown code -> 422; MANUAL_REVIEW case -> 409; no rows written."""
    declined = motor_application(api_client, 16)
    review = motor_application(api_client, 12)
    short = api_client.post(_url(declined), json={**OVERRIDE, "comment": "ok"}, headers=ADMIN)
    assert short.status_code == 422
    assert short.json()["error"]["details"][0]["code"] == "OUT_OF_RANGE"
    long = api_client.post(_url(declined), json={**OVERRIDE, "comment": "x" * 501}, headers=ADMIN)
    assert long.status_code == 422
    bad_code = {**OVERRIDE, "reason_code": "HH-UW-001"}
    unknown = api_client.post(_url(declined), json=bad_code, headers=ADMIN)
    assert unknown.status_code == 422
    assert unknown.json()["error"]["details"][0]["code"] == "UNKNOWN_REASON_CODE"
    wrong_state = api_client.post(_url(review), json=OVERRIDE, headers=ADMIN)
    assert wrong_state.status_code == 409
    assert wrong_state.json()["error"]["code"] == "INVALID_APPLICATION_STATE"
    assert _count(seeded_engine, UnderwritingOverride) == 0
    assert _count(seeded_engine, AuditRecord) == 0


@pytest.mark.ac("AC-09")
def test_ac09_override_requires_admin(api_client: TestClient) -> None:
    """AC-09: 401 without headers; 403 for UNDERWRITER and CUSTOMER; DECLINED queue admin-only."""
    app_id = motor_application(api_client, 16)
    assert api_client.post(_url(app_id), json=OVERRIDE).status_code == 401
    for role in (ActorRole.UNDERWRITER, ActorRole.CUSTOMER):
        response = api_client.post(_url(app_id), json=OVERRIDE, headers=actor_headers(role))
        assert response.status_code == 403
    uw = actor_headers(ActorRole.UNDERWRITER)
    assert api_client.get("/api/underwriting/queue?status=DECLINED", headers=uw).status_code == 403


@pytest.mark.ac("AC-09")
def test_ac09_admin_queue_shows_review_and_declined_with_history(api_client: TestClient) -> None:
    """AC-09: ADMIN queue lists MANUAL_REVIEW and DECLINED cases with their decision history."""
    review = motor_application(api_client, 12)
    declined = motor_application(api_client, 16)
    motor_application(api_client, 3)
    response = api_client.get("/api/underwriting/queue", headers=ADMIN)
    assert response.status_code == 200
    items = {item["application_id"]: item for item in response.json()}
    assert set(items) == {review, declined}
    assert items[declined]["status"] == "DECLINED"
    assert len(items[declined]["decisions"]) == 1
    only_declined = api_client.get("/api/underwriting/queue?status=DECLINED", headers=ADMIN)
    assert [i["application_id"] for i in only_declined.json()] == [declined]
    bad = api_client.get("/api/underwriting/queue?status=ISSUED", headers=ADMIN)
    assert bad.status_code == 422
