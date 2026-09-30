"""AC-22 acceptance tests for the role-header auth stub (NFR-04).

The probe route is ``GET /api/admin/ping`` (ADMIN only) — the auth-boundary probe that
exists until the real admin routes land.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app

PROBE_PATH = "/api/admin/ping"


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


@pytest.mark.ac("AC-22")
def test_ac22_missing_both_headers_is_unauthenticated(client: TestClient) -> None:
    """AC-22: a role-protected route called without actor headers returns 401 UNAUTHENTICATED."""
    response = client.get(PROBE_PATH)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.json()["error"]["details"] is None


@pytest.mark.ac("AC-22")
def test_ac22_missing_role_header_is_unauthenticated(client: TestClient) -> None:
    """AC-22: X-Actor-Id without X-Actor-Role returns 401 UNAUTHENTICATED."""
    response = client.get(PROBE_PATH, headers={"X-Actor-Id": "admin-001"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-22")
def test_ac22_missing_actor_id_header_is_unauthenticated(client: TestClient) -> None:
    """AC-22: X-Actor-Role without X-Actor-Id returns 401 UNAUTHENTICATED."""
    response = client.get(PROBE_PATH, headers={"X-Actor-Role": "ADMIN"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-22")
def test_ac22_blank_headers_are_unauthenticated(client: TestClient) -> None:
    """AC-22: blank actor headers are treated as missing — 401 UNAUTHENTICATED."""
    response = client.get(PROBE_PATH, headers={"X-Actor-Id": "  ", "X-Actor-Role": "ADMIN"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-22")
def test_ac22_unknown_role_is_unauthenticated(client: TestClient) -> None:
    """AC-22: an X-Actor-Role outside CUSTOMER|UNDERWRITER|ADMIN returns 401."""
    response = client.get(PROBE_PATH, headers={"X-Actor-Id": "admin-001", "X-Actor-Role": "ROOT"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-22")
def test_ac22_system_role_from_header_is_unauthenticated(client: TestClient) -> None:
    """AC-22: DEC-010 — SYSTEM is internal and is never accepted from the header (401)."""
    response = client.get(
        PROBE_PATH, headers={"X-Actor-Id": "system-eod", "X-Actor-Role": "SYSTEM"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-22")
def test_ac22_customer_on_admin_route_is_forbidden(client: TestClient) -> None:
    """AC-22: a CUSTOMER calling an ADMIN route returns 403 FORBIDDEN."""
    response = client.get(
        PROBE_PATH, headers={"X-Actor-Id": "cust-001", "X-Actor-Role": "CUSTOMER"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.ac("AC-22")
def test_ac22_underwriter_on_admin_route_is_forbidden(client: TestClient) -> None:
    """AC-22: an UNDERWRITER calling an ADMIN-only route returns 403 FORBIDDEN."""
    headers = {"X-Actor-Id": "uw-001", "X-Actor-Role": "UNDERWRITER"}
    response = client.get(PROBE_PATH, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.ac("AC-22")
def test_ac22_admin_is_allowed_and_actor_is_resolved(client: TestClient) -> None:
    """AC-22: ADMIN gets 200 and the handler receives the resolved actor id and role."""
    response = client.get(PROBE_PATH, headers={"X-Actor-Id": "cust-001", "X-Actor-Role": "ADMIN"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "actor_id": "cust-001", "actor_role": "ADMIN"}


@pytest.mark.ac("AC-22")
def test_ac22_health_still_needs_no_headers(client: TestClient) -> None:
    """AC-22: the auth stub guards /api routes only — /health stays public."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.ac("AC-22")
def test_ac22_role_checks_live_only_in_the_api_layer() -> None:
    """AC-22: no src/service or src/domain module reads X-Actor-Role or imports fastapi."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    offenders: list[str] = []
    for layer in ("service", "domain"):
        for path in sorted((src / layer).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "X-Actor" in text or "fastapi" in text:
                offenders.append(path.as_posix())
    assert not offenders, offenders
