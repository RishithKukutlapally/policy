"""Unit tests for the canonical API error envelope and handlers."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.api import errors


def _body(response: Any) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(response.body)
    return payload


def test_error_body_shape() -> None:
    assert errors.error_body("NOT_FOUND", "gone") == {
        "error": {"code": "NOT_FOUND", "message": "gone", "details": None}
    }


def test_error_response_status_and_payload() -> None:
    response = errors.error_response(404, errors.NOT_FOUND, "gone", {"id": "x"})
    assert response.status_code == 404
    assert _body(response)["error"]["details"] == {"id": "x"}


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [
        ("missing", "REQUIRED"),
        ("extra_forbidden", "UNKNOWN_FIELD"),
        ("greater_than", "OUT_OF_RANGE"),
        ("string_pattern_mismatch", "INVALID_FORMAT"),
        ("something_else", "INVALID_FORMAT"),
    ],
)
def test_detail_code_mapping(raw_type: str, expected: str) -> None:
    assert errors._detail_code(raw_type) == expected


def test_field_path_strips_request_part() -> None:
    assert errors._field_path(("body", "kyc", "pan")) == "kyc.pan"
    assert errors._field_path(("body",)) == "body"


class _Payload(BaseModel):
    amount: str


def _app() -> FastAPI:
    app = FastAPI()
    errors.register_exception_handlers(app)

    @app.post("/api/echo")
    def echo(payload: _Payload) -> dict[str, str]:
        return {"amount": payload.amount}

    @app.get("/api/missing")
    def missing() -> None:
        raise HTTPException(status_code=404, detail="Policy not found")

    @app.get("/api/teapot")
    def teapot() -> None:
        raise HTTPException(status_code=418, detail="teapot")

    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    return app


def test_validation_error_returns_422_with_field_details() -> None:
    client = TestClient(_app())
    response = client.post("/api/echo", json={})
    assert response.status_code == 422
    envelope = response.json()["error"]
    assert envelope["code"] == errors.VALIDATION_ERROR
    assert envelope["details"] == [{"field": "amount", "code": "REQUIRED"}]


def test_http_exception_maps_to_not_found() -> None:
    client = TestClient(_app())
    response = client.get("/api/missing")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": errors.NOT_FOUND, "message": "Policy not found", "details": None}
    }


def test_unmapped_status_falls_back_to_internal_error() -> None:
    response = errors.http_exception_handler(
        None,  # type: ignore[arg-type]
        HTTPException(status_code=418, detail={"unexpected": True}),
    )
    assert _body(response)["error"]["code"] == errors.INTERNAL_ERROR


def test_unhandled_exception_returns_500_envelope() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    response = client.get("/api/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == errors.INTERNAL_ERROR


def test_validation_handler_handles_missing_location() -> None:
    exc = RequestValidationError([{"loc": (), "msg": "bad", "type": "missing"}])
    response = errors.validation_exception_handler(None, exc)  # type: ignore[arg-type]
    assert _body(response)["error"]["details"] == [{"field": "body", "code": "REQUIRED"}]
