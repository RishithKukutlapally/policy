"""AC-11: rule-version lifecycle over the API — draft, replace (DEC-009), publish, immutability."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.types.enums import ActorRole, ProductCode
from tests.conftest import actor_headers, rule_body

MOTOR_VERSIONS = "/api/products/MOTOR/versions"
ADMIN = actor_headers(ActorRole.ADMIN)


def _versions(client: TestClient) -> list[dict[str, Any]]:
    """MOTOR's version list as ADMIN."""
    response = client.get(MOTOR_VERSIONS, headers=ADMIN)
    assert response.status_code == 200, response.text
    body: list[dict[str, Any]] = response.json()
    return body


def _create_draft(client: TestClient, **kwargs: str) -> Any:
    """POST a valid MOTOR draft body."""
    return client.post(MOTOR_VERSIONS, json=rule_body(**kwargs), headers=ADMIN)


@pytest.mark.ac("AC-11")
def test_ac11_create_draft_appends_version_two_as_draft(api_client: TestClient) -> None:
    """AC-11: a valid body becomes v2 DRAFT while v1 stays the active version."""
    response = _create_draft(api_client)
    assert response.status_code == 201, response.text
    assert response.json() == {"product": "MOTOR", "version": 2, "status": "DRAFT"}
    versions = _versions(api_client)
    assert [(v["version"], v["status"], v["is_active"]) for v in versions] == [
        (1, "PUBLISHED", True),
        (2, "DRAFT", False),
    ]
    assert versions[1]["actor_id"] == "admin-001"


@pytest.mark.ac("AC-11")
def test_ac11_second_draft_conflicts_with_the_open_one(api_client: TestClient) -> None:
    """AC-11: only one open DRAFT per product (409 DRAFT_ALREADY_OPEN)."""
    assert _create_draft(api_client).status_code == 201
    response = _create_draft(api_client, base_rate="0.0340")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DRAFT_ALREADY_OPEN"
    assert len(_versions(api_client)) == 2


@pytest.mark.ac("AC-11")
def test_ac11_put_replaces_the_open_draft_and_increments_the_revision(
    api_client: TestClient,
) -> None:
    """AC-11 (DEC-009): PUT appends revision 2 of the same version with the new body."""
    assert _create_draft(api_client).status_code == 201
    response = api_client.put(
        f"{MOTOR_VERSIONS}/2", json=rule_body(base_rate="0.0330"), headers=ADMIN
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"product": "MOTOR", "version": 2, "status": "DRAFT"}
    latest = _versions(api_client)[1]
    assert latest["revision"] == 2
    assert latest["status"] == "DRAFT"
    assert latest["rules"]["premium"]["base_rate"] == "0.0330"


@pytest.mark.ac("AC-11")
def test_ac11_publish_makes_the_version_active(api_client: TestClient) -> None:
    """AC-11: publishing a DRAFT appends a PUBLISHED row that becomes the active version."""
    assert _create_draft(api_client).status_code == 201
    response = api_client.post(f"{MOTOR_VERSIONS}/2/publish", headers=ADMIN)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "product": "MOTOR",
        "version": 2,
        "status": "PUBLISHED",
        "is_active": True,
    }
    versions = _versions(api_client)
    assert [(v["version"], v["status"], v["is_active"]) for v in versions] == [
        (1, "PUBLISHED", False),
        (2, "PUBLISHED", True),
    ]
    products = api_client.get("/api/products", headers=ADMIN).json()
    assert {p["product"]: p["active_version"] for p in products}["MOTOR"] == 2


@pytest.mark.ac("AC-11")
def test_ac11_publishing_twice_is_rejected_as_immutable(api_client: TestClient) -> None:
    """AC-11: a PUBLISHED version can never be published again (409 VERSION_IMMUTABLE)."""
    assert _create_draft(api_client).status_code == 201
    assert api_client.post(f"{MOTOR_VERSIONS}/2/publish", headers=ADMIN).status_code == 200
    response = api_client.post(f"{MOTOR_VERSIONS}/2/publish", headers=ADMIN)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_IMMUTABLE"


@pytest.mark.ac("AC-11")
def test_ac11_put_on_a_published_version_is_rejected_as_immutable(api_client: TestClient) -> None:
    """AC-11: PUT on the PUBLISHED v1 changes nothing (409 VERSION_IMMUTABLE)."""
    before = _versions(api_client)[0]
    response = api_client.put(
        f"{MOTOR_VERSIONS}/1", json=rule_body(base_rate="0.9900"), headers=ADMIN
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_IMMUTABLE"
    after = _versions(api_client)
    assert len(after) == 1
    assert after[0]["rules"] == before["rules"]


@pytest.mark.ac("AC-11")
def test_ac11_malformed_rule_body_names_the_offending_field(api_client: TestClient) -> None:
    """AC-11: a numeric base_rate is 422 VALIDATION_ERROR naming ``premium.base_rate``."""
    body = rule_body()
    body["premium"]["base_rate"] = 0.032
    response = api_client.post(MOTOR_VERSIONS, json=body, headers=ADMIN)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    fields = {detail["field"]: detail["code"] for detail in error["details"]}
    assert "premium.base_rate" in fields
    assert fields["premium.base_rate"] == "MONEY_MUST_BE_STRING"
    assert len(_versions(api_client)) == 1


@pytest.mark.ac("AC-11")
def test_ac11_body_for_another_product_is_rejected(api_client: TestClient) -> None:
    """AC-11: a HOUSEHOLD body posted to MOTOR is 422 on the ``product`` field."""
    response = api_client.post(MOTOR_VERSIONS, json=rule_body(ProductCode.HOUSEHOLD), headers=ADMIN)
    assert response.status_code == 422, response.text
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert "product" in fields
    assert len(_versions(api_client)) == 1


@pytest.mark.ac("AC-11")
def test_ac11_eligibility_bounds_are_checked(api_client: TestClient) -> None:
    """AC-11: ``min_age > max_age`` is 422 OUT_OF_RANGE on ``eligibility.min_age``."""
    body = rule_body()
    body["eligibility"]["min_age"] = 80
    response = api_client.post(MOTOR_VERSIONS, json=body, headers=ADMIN)
    assert response.status_code == 422, response.text
    fields = {d["field"]: d["code"] for d in response.json()["error"]["details"]}
    assert fields["eligibility.min_age"] == "OUT_OF_RANGE"


@pytest.mark.ac("AC-11")
def test_ac11_unknown_product_and_version_are_not_found(api_client: TestClient) -> None:
    """AC-11: unknown product or version is 404 NOT_FOUND on every catalog write."""
    unknown_product = api_client.post(
        "/api/products/SPACESHIP/versions", json=rule_body(), headers=ADMIN
    )
    assert unknown_product.status_code == 404
    assert unknown_product.json()["error"]["code"] == "NOT_FOUND"
    unknown_version = api_client.post(f"{MOTOR_VERSIONS}/9/publish", headers=ADMIN)
    assert unknown_version.status_code == 404
    assert unknown_version.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.ac("AC-11")
@pytest.mark.parametrize("role", [ActorRole.CUSTOMER, ActorRole.UNDERWRITER])
def test_ac11_non_admins_may_not_write_versions(api_client: TestClient, role: ActorRole) -> None:
    """AC-11/AC-22: CUSTOMER and UNDERWRITER get 403 on every catalog write."""
    headers = actor_headers(role)
    assert api_client.post(MOTOR_VERSIONS, json=rule_body(), headers=headers).status_code == 403
    assert (
        api_client.put(f"{MOTOR_VERSIONS}/1", json=rule_body(), headers=headers).status_code == 403
    )
    publish = api_client.post(f"{MOTOR_VERSIONS}/1/publish", headers=headers)
    assert publish.status_code == 403
    assert publish.json()["error"]["code"] == "FORBIDDEN"
    assert len(_versions(api_client)) == 1


@pytest.mark.ac("AC-11")
def test_ac11_catalog_writes_require_actor_headers(api_client: TestClient) -> None:
    """AC-11/AC-22: no actor headers means 401 UNAUTHENTICATED, nothing written."""
    for response in (
        api_client.post(MOTOR_VERSIONS, json=rule_body()),
        api_client.put(f"{MOTOR_VERSIONS}/1", json=rule_body()),
        api_client.post(f"{MOTOR_VERSIONS}/1/publish"),
    ):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert len(_versions(api_client)) == 1
