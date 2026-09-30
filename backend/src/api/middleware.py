"""HTTP middleware: correlation id binding, security headers and the access log (NFR-06).

Reads ``X-Correlation-ID`` from the request (or mints a UUID4), binds it for the duration
of the request so every log line carries it, echoes it on the response — including error
responses — and writes exactly one access line. The access line holds no PII and no query
values (docs/conventions.md -> "API / auth stub").

A client-supplied correlation id is adopted only when it matches :data:`_CORRELATION_ID_PATTERN`
(a UUID passes); anything longer than 64 characters or carrying a character outside
``A-Za-z0-9._-`` is discarded and a fresh id is minted, so a caller cannot steer an arbitrary
string into every log line of a request or into a response header.

The same middleware sets the conservative security response headers on *every* response,
error responses included.
"""

from __future__ import annotations

import re
import time
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.lib.correlation import (
    CORRELATION_ID_HEADER,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from src.lib.logging import get_logger

_NANOSECONDS_PER_MILLISECOND = 1_000_000
_ACCESS_LOGGER = get_logger("policyforge.access")

#: A correlation id is adopted from the client only in this conservative, bounded shape.
_CORRELATION_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

#: Security response headers set on every response, including error responses (APP-W03).
SECURITY_HEADERS: Final[dict[str, str]] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'",
}


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a correlation id per request, echo it, harden the response, and log one line."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Run the request with a bound correlation id and emit the access log line."""
        correlation_id = _incoming_correlation_id(request) or new_correlation_id()
        token = set_correlation_id(correlation_id)
        started_ns = time.perf_counter_ns()
        try:
            try:
                response = await call_next(request)
            except Exception:
                _log_access(request, 500, started_ns)
                raise
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            _apply_security_headers(response)
            _log_access(request, response.status_code, started_ns)
            return response
        finally:
            reset_correlation_id(token)


def _apply_security_headers(response: Response) -> None:
    """Set the security headers without overwriting one a handler set deliberately."""
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)


def _incoming_correlation_id(request: Request) -> str | None:
    """Return the client-supplied correlation id when it is well formed, else ``None``."""
    raw = request.headers.get(CORRELATION_ID_HEADER)
    if raw is None:
        return None
    candidate = raw.strip()
    return candidate if _CORRELATION_ID_PATTERN.match(candidate) else None


def _elapsed_ms(started_ns: int) -> int:
    """Whole milliseconds elapsed since ``started_ns`` (integer maths, never float)."""
    return (time.perf_counter_ns() - started_ns) // _NANOSECONDS_PER_MILLISECOND


def _log_access(request: Request, status: int, started_ns: int) -> None:
    """Write the single access line for a finished request."""
    _ACCESS_LOGGER.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": _elapsed_ms(started_ns),
        },
    )
