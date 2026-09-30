"""AC-16: the endorsement API validates on the policy's rule version and previews the delta."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.config.rule_loader import load_rule_file
from src.domain.endorsement_rules import premium_delta
from src.repository.models import (
    AuditRecord,
    Endorsement,
    PolicyStateTransition,
    RuleSetVersion,
)
from src.types.enums import ActorRole, ProductCode
from tests.endorsement_helpers import (
    ADDRESS_BODY,
    NOMINEE_BODY,
    SUM_BODY,
    count,
    endorse,
    issued_policy,
    policy_row,
)

_MOTOR_BASE: dict[str, Any] = {
    "owner_age": 30,
    "vehicle_age_years": 2,
    "engine_cc": 998,
    "zone": "B",
    "ncb_percent": "0",
}


def _codes(body: dict[str, Any]) -> set[tuple[str, str]]:
    return {(d["field"], d["code"]) for d in body["error"]["details"]}


@pytest.mark.ac("AC-16")
@pytest.mark.parametrize("body", [ADDRESS_BODY, NOMINEE_BODY, SUM_BODY])
def test_ac16_all_three_types_succeed(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, body: dict[str, str]
) -> None:
    number = issued_policy(api_client, monkeypatch)
    response = endorse(api_client, number, body)
    assert response.status_code == 201, response.text
    assert response.json()["type"] == body["type"]
    assert response.json()["policy"]["status"] == "ENDORSED"


@pytest.mark.ac("AC-16")
def test_ac16_preview_persists_nothing(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    models = (Endorsement, PolicyStateTransition, AuditRecord)
    before = {m: count(seeded_engine, m) for m in models}
    response = endorse(api_client, number, SUM_BODY, role=ActorRole.ADMIN, preview=True)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["preview"] is True
    assert body["premium_delta"] == "1537.26"
    assert body["new_premium"] == "18600.00"
    assert body["after"]["sum_insured"] == "600000.00"
    assert {m: count(seeded_engine, m) for m in models} == before
    policy = policy_row(seeded_engine, number)
    assert (policy.status, policy.premium) == ("ACTIVE", Decimal("15500.00"))


@pytest.mark.ac("AC-16")
def test_ac16_delta_matches_domain_calculation(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    expected = premium_delta(
        load_rule_file(ProductCode.MOTOR, 1),
        {**_MOTOR_BASE, "sum_insured": Decimal("500000.00")},
        {**_MOTOR_BASE, "sum_insured": Decimal("600000.00")},
        181,
        365,
    )
    response = endorse(api_client, number, SUM_BODY, preview=True)
    assert Decimal(response.json()["premium_delta"]) == expected == Decimal("1537.26")


@pytest.mark.ac("AC-16")
@pytest.mark.parametrize("body", [ADDRESS_BODY, NOMINEE_BODY])
def test_ac16_non_priced_types_have_zero_delta(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, body: dict[str, str]
) -> None:
    number = issued_policy(api_client, monkeypatch)
    response = endorse(api_client, number, body)
    assert response.json()["premium_delta"] == "0.00"
    assert response.json()["new_premium"] == "15500.00"


@pytest.mark.ac("AC-16")
def test_ac16_sum_insured_out_of_range_is_422(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    response = endorse(api_client, number, {**SUM_BODY, "new_sum_insured": "99999999.00"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert ("new_sum_insured", "OUT_OF_RANGE") in _codes(response.json())


@pytest.mark.ac("AC-16")
def test_ac16_type_not_allowed_is_422(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        for row in session.query(RuleSetVersion).all():
            content = dict(row.content)
            content["endorsement"] = {"allowed_types": ["CHANGE_ADDRESS"]}
            row.content = content
        session.commit()
    response = endorse(api_client, number, NOMINEE_BODY)
    assert response.status_code == 422
    assert ("endorsement_type", "NOT_ALLOWED") in _codes(response.json())


@pytest.mark.ac("AC-16")
def test_ac16_role_unknown_type_and_missing_policy(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    assert endorse(api_client, number, ADDRESS_BODY, role=ActorRole.UNDERWRITER).status_code == 403
    unknown = endorse(api_client, number, {"type": "DELETE_POLICY"})
    assert unknown.status_code == 422
    assert ("type", "UNKNOWN_CODE") in _codes(unknown.json())
    assert endorse(api_client, "MO-2026-999999", ADDRESS_BODY).status_code == 404
