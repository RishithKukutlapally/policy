"""AC-02: the catalog API lists the three products, each with an active PUBLISHED rule set."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.types.enums import ActorRole, ProductCode
from tests.conftest import actor_headers

PRODUCT_ORDER = ("TERM_LIFE", "MOTOR", "HOUSEHOLD")
EXPECTED_NAMES = {"TERM_LIFE": "Term Life", "MOTOR": "Motor", "HOUSEHOLD": "Household"}


def _products(client: TestClient, role: ActorRole) -> list[dict[str, Any]]:
    """GET /api/products as ``role``, asserting 200."""
    response = client.get("/api/products", headers=actor_headers(role))
    assert response.status_code == 200, response.text
    body: list[dict[str, Any]] = response.json()
    return body


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("role", list(ActorRole)[:3])
def test_ac02_products_are_listed_for_every_header_role(
    api_client: TestClient, role: ActorRole
) -> None:
    """AC-02: every valid role may read the catalog."""
    products = _products(api_client, role)
    assert [entry["product"] for entry in products] == list(PRODUCT_ORDER)


@pytest.mark.ac("AC-02")
def test_ac02_each_product_reports_an_active_published_version(api_client: TestClient) -> None:
    """AC-02: after the seed import every product's active version is v1 in INR."""
    for entry in _products(api_client, ActorRole.CUSTOMER):
        assert entry["active_version"] == 1
        assert entry["currency"] == "INR"
        assert entry["name"] == EXPECTED_NAMES[entry["product"]]
        assert set(entry) == {"product", "name", "active_version", "currency"}


@pytest.mark.ac("AC-02")
def test_ac02_products_require_actor_headers(api_client: TestClient) -> None:
    """AC-02: the catalog is not public — no headers means 401."""
    response = api_client.get("/api/products")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-02")
def test_ac02_versions_endpoint_marks_v1_published_and_active(api_client: TestClient) -> None:
    """AC-02: MOTOR's version list carries v1 PUBLISHED, active, with its rule body."""
    response = api_client.get(
        "/api/products/MOTOR/versions", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert response.status_code == 200, response.text
    versions: list[dict[str, Any]] = response.json()
    assert len(versions) == 1
    only = versions[0]
    assert only["product"] == "MOTOR"
    assert (only["version"], only["revision"], only["status"]) == (1, 1, "PUBLISHED")
    assert only["is_active"] is True
    assert only["effective_from"] == "2026-01-01"
    assert only["created_at"].endswith("Z")
    assert only["actor_id"] == "SYSTEM"
    assert only["rules"]["premium"]["base_rate"] == "0.0310"


@pytest.mark.ac("AC-02")
def test_ac02_each_product_exposes_a_distinct_rule_set(api_client: TestClient) -> None:
    """AC-02: the three products' active rule bodies differ in base rate and factor keys."""
    base_rates: set[str] = set()
    factor_keys: set[frozenset[str]] = set()
    for product in ProductCode:
        response = api_client.get(
            f"/api/products/{product.value}/versions", headers=actor_headers(ActorRole.ADMIN)
        )
        assert response.status_code == 200, response.text
        rules = response.json()[0]["rules"]
        assert rules["product"] == product.value
        base_rates.add(rules["premium"]["base_rate"])
        factor_keys.add(frozenset(rules["premium"]["factors"]))
    assert len(base_rates) == 3
    assert len(factor_keys) == 3


@pytest.mark.ac("AC-02")
def test_ac02_unknown_product_is_not_found(api_client: TestClient) -> None:
    """AC-02: an unknown product code is a 404, never a 500."""
    response = api_client.get(
        "/api/products/SPACESHIP/versions", headers=actor_headers(ActorRole.CUSTOMER)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
