"""AC-21 acceptance tests for the un-prefixed GET /health endpoint."""

from __future__ import annotations

import time

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


@pytest.mark.ac("AC-21")
def test_ac21_health_returns_ok(client: TestClient) -> None:
    """AC-21: GET /health returns HTTP 200 with JSON body {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _api_route_paths() -> set[str]:
    """Every application route path, taken from the generated OpenAPI schema."""
    paths = set(app.openapi()["paths"])
    paths |= {route.path for route in app.router.routes if isinstance(route, APIRoute)}
    return paths


@pytest.mark.ac("AC-21")
def test_ac21_health_is_the_only_unprefixed_route() -> None:
    """AC-21: /health is the only route not under the /api prefix."""
    paths = _api_route_paths()
    assert "/health" in paths
    assert {path for path in paths if not path.startswith("/api")} == {"/health"}


@pytest.mark.ac("AC-21")
def test_ac21_health_needs_no_auth_headers(client: TestClient) -> None:
    """AC-21: /health is public — no X-Actor-Id / X-Actor-Role required."""
    assert client.get("/health", headers={}).status_code == 200


@pytest.mark.ac("AC-21")
def test_ac21_health_responds_within_one_second(client: TestClient) -> None:
    """AC-21: the first GET /health after startup answers within 1 s (NFR-07)."""
    started = time.perf_counter()
    response = client.get("/health")
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 1.0, f"/health took {elapsed:.3f}s"


@pytest.mark.ac("AC-21")
def test_ac21_health_does_no_database_work(client: TestClient, tmp_path: object) -> None:
    """AC-21: /health performs no database work, so it answers before migrations run."""
    import src.repository.database as database

    def _fail() -> object:
        raise AssertionError("/health must not open a database session")

    original = database.SessionLocal
    database.SessionLocal = _fail  # type: ignore[assignment]
    try:
        assert client.get("/health").status_code == 200
    finally:
        database.SessionLocal = original  # type: ignore[assignment]
