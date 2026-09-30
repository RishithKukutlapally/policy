"""AC-23 acceptance tests: correlation id, structured JSON logs and PII redaction."""

from __future__ import annotations

import ast
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.lib.logging import get_logger, mask_pii
from src.main import app

CORRELATION_HEADER = "X-Correlation-ID"
SYNTHETIC_AADHAAR = "999900000001"
SYNTHETIC_PAN = "AAAAA0001A"


@pytest.fixture(name="client")
def _client() -> TestClient:
    return TestClient(app)


def _json_lines(captured: str) -> list[dict[str, Any]]:
    """Parse every non-empty captured stdout line as a JSON object."""
    lines = [line for line in captured.splitlines() if line.strip()]
    parsed: list[dict[str, Any]] = []
    for line in lines:
        payload = json.loads(line)
        assert isinstance(payload, dict), f"log line is not a JSON object: {line}"
        parsed.append(payload)
    return parsed


@pytest.mark.ac("AC-23")
def test_ac23_supplied_correlation_id_is_echoed(client: TestClient) -> None:
    """AC-23: a request carrying X-Correlation-ID gets the same value back."""
    response = client.get("/health", headers={CORRELATION_HEADER: "test-corr-001"})
    assert response.status_code == 200
    assert response.headers[CORRELATION_HEADER] == "test-corr-001"


@pytest.mark.ac("AC-23")
def test_ac23_missing_correlation_id_is_generated_as_uuid4(client: TestClient) -> None:
    """AC-23: a request without the header receives a freshly generated UUID4."""
    response = client.get("/health")
    generated = response.headers[CORRELATION_HEADER]
    assert uuid.UUID(generated).version == 4


@pytest.mark.ac("AC-23")
def test_ac23_error_response_also_carries_correlation_id(client: TestClient) -> None:
    """AC-23: a 404 response still carries X-Correlation-ID."""
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert uuid.UUID(response.headers[CORRELATION_HEADER]).version == 4


@pytest.mark.ac("AC-23")
def test_ac23_every_log_line_is_json_with_the_correlation_id(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-23: each log line is one JSON object with the five canonical keys."""
    client.get("/health", headers={CORRELATION_HEADER: "test-corr-002"})
    lines = _json_lines(capsys.readouterr().out)
    assert lines, "the request produced no log output"
    for payload in lines:
        assert {"timestamp", "level", "logger", "message", "correlation_id"} <= set(payload)
        assert payload["correlation_id"] == "test-corr-002"


@pytest.mark.ac("AC-23")
def test_ac23_access_log_records_method_path_and_status(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-23: the access log line carries method, path, status and duration_ms."""
    client.get("/health?secret=leak", headers={CORRELATION_HEADER: "test-corr-003"})
    lines = _json_lines(capsys.readouterr().out)
    access = [line for line in lines if line.get("path") == "/health"]
    assert len(access) == 1
    assert access[0]["method"] == "GET"
    assert access[0]["status"] == 200
    assert isinstance(access[0]["duration_ms"], int)
    assert "leak" not in json.dumps(access[0])


@pytest.mark.ac("AC-23")
def test_ac23_mask_pii_masks_aadhaar_and_pan() -> None:
    """AC-23: mask_pii renders synthetic Aadhaar and PAN in their canonical masked forms."""
    assert mask_pii(SYNTHETIC_AADHAAR) == "XXXX-XXXX-0001"
    masked_pan = mask_pii(f"pan={SYNTHETIC_PAN}")
    assert SYNTHETIC_PAN not in masked_pan
    assert "XXXXX0001X" in masked_pan
    assert mask_pii("no pii here") == "no pii here"


@pytest.mark.ac("AC-23")
def test_ac23_logger_never_emits_raw_pii(capsys: pytest.CaptureFixture[str]) -> None:
    """AC-23: Aadhaar, PAN and health declarations never reach a log line raw."""
    get_logger("t").info(
        "kyc",
        extra={
            "aadhaar": SYNTHETIC_AADHAAR,
            "pan": SYNTHETIC_PAN,
            "health_declaration": {"condition": "asthma"},
        },
    )
    out = capsys.readouterr().out
    assert SYNTHETIC_AADHAAR not in out
    assert SYNTHETIC_PAN not in out
    assert "asthma" not in out
    assert "[REDACTED]" in out
    payload = _json_lines(out)[0]
    assert payload["aadhaar"] == "XXXX-XXXX-0001"
    assert payload["pan"] == "XXXXX0001X"


@pytest.mark.ac("AC-23")
def test_ac23_raw_pii_in_a_message_is_masked(capsys: pytest.CaptureFixture[str]) -> None:
    """AC-23: PII accidentally interpolated into the message is masked too."""
    get_logger("t").info("applicant %s filed", mask_pii(SYNTHETIC_AADHAAR))
    out = capsys.readouterr().out
    assert SYNTHETIC_AADHAAR not in out
    assert "XXXX-XXXX-0001" in out


@pytest.mark.ac("AC-23")
def test_ac23_access_line_is_logged_when_the_request_explodes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC-23: a crashing request still logs one access line with status 500."""
    from fastapi import FastAPI

    from src.api.middleware import CorrelationIdMiddleware

    crashing = FastAPI()
    crashing.add_middleware(CorrelationIdMiddleware)

    @crashing.get("/boom")
    def _boom() -> None:
        raise RuntimeError("boom")

    with TestClient(crashing, raise_server_exceptions=False) as crash_client:
        response = crash_client.get("/boom", headers={CORRELATION_HEADER: "test-corr-004"})
    assert response.status_code == 500
    access = [line for line in _json_lines(capsys.readouterr().out) if line.get("path") == "/boom"]
    assert len(access) == 1
    assert access[0]["status"] == 500
    assert access[0]["correlation_id"] == "test-corr-004"


def _imported_top_level_modules(path: Path) -> set[str]:
    """Collect the top-level names of every absolute import in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.ac("AC-23")
@pytest.mark.parametrize("module", ["logging.py", "correlation.py"])
def test_ac23_lib_modules_import_stdlib_only(module: str) -> None:
    """AC-23: src/lib stays standard-library only (no fastapi, sqlalchemy or src.*)."""
    path = Path(__file__).resolve().parents[2] / "src" / "lib" / module
    imported = _imported_top_level_modules(path)
    non_stdlib = imported - set(sys.stdlib_module_names) - {"__future__"}
    assert non_stdlib == set(), f"{module} imports non-stdlib modules: {sorted(non_stdlib)}"
