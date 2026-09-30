"""Per-request correlation id (NFR-06).

Standard library only (docs/conventions.md -> "Layer import rules"). The id is held in a
:class:`~contextvars.ContextVar` so it is bound per request/task without being threaded
through every function signature; the API middleware sets it and the JSON logger reads it.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token

CORRELATION_ID_HEADER = "X-Correlation-ID"

_correlation_id: ContextVar[str | None] = ContextVar("policyforge_correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Return the correlation id bound to the current context, or ``None``."""
    return _correlation_id.get()


def set_correlation_id(value: str) -> Token[str | None]:
    """Bind ``value`` as the current correlation id, returning a reset token."""
    return _correlation_id.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation id that was bound before ``token`` was issued."""
    _correlation_id.reset(token)


def new_correlation_id() -> str:
    """Generate a fresh UUID4 correlation id."""
    return str(uuid.uuid4())
