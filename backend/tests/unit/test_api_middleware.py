"""Unit tests for the API-layer middleware: correlation id hygiene and security headers.

Covers the hardening of APP-W02 (an inbound ``X-Correlation-ID`` is validated and length
bounded before it is logged or echoed) and APP-W03 (every response, including an error
response, carries the conservative security headers).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.api.middleware import _incoming_correlation_id
from src.main import app

CORRELATION_HEADER = "X-Correlation-ID"
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'",
}


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(
    "supplied",
    [
        "0f6a9b2c-3d4e-4f50-8a1b-2c3d4e5f6071",
        "corr-uw-1",
        "A.b_c-9",
        "x" * 64,
    ],
)
def test_well_formed_correlation_id_is_adopted(client: TestClient, supplied: str) -> None:
    """APP-W02: a conservative, bounded id (a UUID included) is still honoured and echoed."""
    response = client.get("/health", headers={CORRELATION_HEADER: supplied})
    assert response.headers[CORRELATION_HEADER] == supplied


@pytest.mark.parametrize(
    "supplied",
    [
        "x" * 65,
        "x" * 5000,
        "has space",
        "bad/slash",
        "semi;colon",
        "pipe|char",
        "   ",
    ],
)
def test_rejected_correlation_id_is_replaced_by_a_fresh_uuid4(
    client: TestClient, supplied: str
) -> None:
    """APP-W02: an over-long, control-character or otherwise odd value is discarded."""
    response = client.get("/health", headers={CORRELATION_HEADER: supplied})
    echoed = response.headers[CORRELATION_HEADER]
    assert echoed != supplied.strip()
    assert uuid.UUID(echoed).version == 4


@pytest.mark.parametrize(
    "supplied", ["ctrl\x01char", "line\nbreak", "tab\there", "unicode-é", "", "   "]
)
def test_control_and_non_ascii_values_are_refused(supplied: str) -> None:
    """APP-W02: values an HTTP client cannot even transmit are refused at the source too."""
    scope = {
        "type": "http",
        "headers": [(CORRELATION_HEADER.lower().encode(), supplied.encode("utf-8"))],
    }
    assert _incoming_correlation_id(Request(scope)) is None


def test_rejected_correlation_id_never_reaches_the_log(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """APP-W02: the discarded client value appears on no log line."""
    marker = "q" * 200
    client.get("/health", headers={CORRELATION_HEADER: marker})
    assert marker not in capsys.readouterr().out


@pytest.mark.parametrize(("name", "value"), sorted(SECURITY_HEADERS.items()))
def test_security_headers_present_on_a_200(client: TestClient, name: str, value: str) -> None:
    """APP-W03: every successful response carries the security headers."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers[name] == value


@pytest.mark.parametrize(("name", "value"), sorted(SECURITY_HEADERS.items()))
def test_security_headers_present_on_a_404(client: TestClient, name: str, value: str) -> None:
    """APP-W03: an error response carries them too."""
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers[name] == value


def test_security_headers_present_on_an_authenticated_error(client: TestClient) -> None:
    """APP-W03: the 401 from the auth stub is also hardened."""
    response = client.get("/api/admin/ping")
    assert response.status_code == 401
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value
