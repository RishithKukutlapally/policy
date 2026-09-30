"""Canonical API error envelope and FastAPI exception handlers.

Every non-2xx response has the shape ``{"error": {"code", "message", "details"}}``
(docs/conventions.md -> "Error codes").
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.types.errors import PolicyForgeError

VALIDATION_ERROR: Final = "VALIDATION_ERROR"
UNAUTHENTICATED: Final = "UNAUTHENTICATED"
FORBIDDEN: Final = "FORBIDDEN"
NOT_FOUND: Final = "NOT_FOUND"
INTERNAL_ERROR: Final = "INTERNAL_ERROR"

_STATUS_TO_CODE: Final[dict[int, str]] = {
    401: UNAUTHENTICATED,
    403: FORBIDDEN,
    404: NOT_FOUND,
    422: VALIDATION_ERROR,
    500: INTERNAL_ERROR,
}

_DETAIL_CODE_BY_PYDANTIC_TYPE: Final[dict[str, str]] = {
    "missing": "REQUIRED",
    "value_error.missing": "REQUIRED",
    "extra_forbidden": "UNKNOWN_FIELD",
    "string_pattern_mismatch": "INVALID_FORMAT",
    "greater_than": "OUT_OF_RANGE",
    "greater_than_equal": "OUT_OF_RANGE",
    "less_than": "OUT_OF_RANGE",
    "less_than_equal": "OUT_OF_RANGE",
}


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    """Build the canonical error envelope."""
    return {"error": {"code": code, "message": message, "details": details}}


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    """Build a JSON response carrying the canonical error envelope."""
    return JSONResponse(status_code=status_code, content=error_body(code, message, details))


def _detail_code(raw_type: str) -> str:
    """Map a pydantic error type to a canonical ``details[].code``."""
    return _DETAIL_CODE_BY_PYDANTIC_TYPE.get(raw_type, "INVALID_FORMAT")


def _field_path(location: tuple[Any, ...]) -> str:
    """Render a pydantic error location as a dotted field path (``kyc.pan``)."""
    parts = [str(part) for part in location if part not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


def validation_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """422 VALIDATION_ERROR listing every failing field at once."""
    assert isinstance(exc, RequestValidationError)
    details = [
        {
            "field": _field_path(tuple(err.get("loc", ()))),
            "code": _detail_code(str(err.get("type"))),
        }
        for err in exc.errors()
    ]
    return error_response(422, VALIDATION_ERROR, "Request validation failed", details)


def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Map Starlette/FastAPI HTTP errors (404, 401, 403, ...) onto the envelope."""
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_TO_CODE.get(exc.status_code, INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ").title()
    return error_response(exc.status_code, code, message)


def policyforge_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Render a typed :class:`~src.types.errors.PolicyForgeError` as its canonical envelope."""
    assert isinstance(exc, PolicyForgeError)
    return error_response(exc.http_status, exc.code, exc.message, exc.details)


def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """500 INTERNAL_ERROR — the transaction rolled back and nothing was persisted."""
    return error_response(500, INTERNAL_ERROR, "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    """Install every canonical exception handler on ``app``."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(PolicyForgeError, policyforge_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
