"""Structured JSON logging with defensive PII redaction (NFR-03, NFR-06).

Every handler installed here writes exactly one JSON object per line with the keys
``timestamp``, ``level``, ``logger``, ``message`` and ``correlation_id`` plus any ``extra``
fields. Aadhaar, PAN, health declarations and KYC documents are masked *inside the
formatter*, so a caller cannot leak them by accident (docs/conventions.md -> "Synthetic
data").

Standard library only: the correlation id is read through a provider callback that
``src/lib/__init__.py`` wires to :mod:`src.lib.correlation`, keeping this module free of
any ``src.*`` import (AC-23).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sys
from collections.abc import Callable
from typing import Any, Final

REDACTED: Final = "[REDACTED]"
LOG_LEVEL: Final = logging.INFO

_AADHAAR_VALUE: Final = re.compile(r"\b(\d{4})[- ]?(\d{4})[- ]?(\d{4})\b")
_PAN_VALUE: Final = re.compile(r"\b([A-Z]{5})(\d{4})([A-Z])\b")
_DIGITS: Final = re.compile(r"\D")

_AADHAAR_KEY: Final = re.compile(r"(^|_)aadh?aar", re.IGNORECASE)
_PAN_KEY: Final = re.compile(r"(^|_)pan(_|$)", re.IGNORECASE)
_OPAQUE_KEY: Final = re.compile(r"health_?decl|medical|kyc_?doc|pre_?existing", re.IGNORECASE)

_RESERVED_RECORD_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "message", "module", "msecs", "msg", "name",
        "pathname", "process", "processName", "relativeCreated", "stack_info",
        "taskName", "thread", "threadName",
    }
)  # fmt: skip


def _no_correlation_id() -> str | None:
    """Default provider: no correlation id is bound outside a request."""
    return None


_correlation_provider: Callable[[], str | None] = _no_correlation_id


def set_correlation_provider(provider: Callable[[], str | None]) -> None:
    """Install the callback the formatter uses to read the current correlation id."""
    global _correlation_provider
    _correlation_provider = provider


def _mask_aadhaar(value: object) -> str:
    """Render an Aadhaar as ``XXXX-XXXX-<last four>``, or ``[REDACTED]`` when unusable."""
    if not isinstance(value, str):
        return REDACTED
    digits = _DIGITS.sub("", value)
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) >= 4 else REDACTED


def _mask_pan(value: object) -> str:
    """Render a PAN as ``XXXXX<four digits>X``, or ``[REDACTED]`` when unusable."""
    if isinstance(value, str):
        match = _PAN_VALUE.fullmatch(value.strip().upper())
        if match is not None:
            return f"XXXXX{match.group(2)}X"
    return REDACTED


def _mask_patterns(text: str) -> str:
    """Mask every Aadhaar- or PAN-shaped substring inside ``text``."""
    masked = _AADHAAR_VALUE.sub(lambda m: f"XXXX-XXXX-{m.group(3)}", text)
    return _PAN_VALUE.sub(lambda m: f"XXXXX{m.group(2)}X", masked)


def mask_pii(value: object, kind: str | None = None) -> str:
    """Mask ``value`` to its canonical display form.

    ``kind`` selects the masking rule (``"aadhaar"``, ``"pan"``, anything else is fully
    opaque). Without a ``kind`` the value is scanned for Aadhaar/PAN shapes and only those
    substrings are replaced, so ordinary messages survive unchanged.
    """
    if kind == "aadhaar":
        return _mask_aadhaar(value)
    if kind == "pan":
        return _mask_pan(value)
    if kind is not None:
        return REDACTED
    return _mask_patterns(value) if isinstance(value, str) else REDACTED


def _kind_for_key(key: str) -> str | None:
    """Return the masking kind a field name implies, or ``None`` when it is not PII."""
    if _OPAQUE_KEY.search(key):
        return "opaque"
    if _AADHAAR_KEY.search(key):
        return "aadhaar"
    if _PAN_KEY.search(key):
        return "pan"
    return None


def _redact_value(value: object) -> Any:
    """Recursively mask PII inside ``value`` without touching non-PII scalars."""
    if isinstance(value, dict):
        return redact({str(key): item for key, item in value.items()})
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _mask_patterns(value)
    return value


def redact(mapping: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``mapping`` with every known PII key masked at any depth."""
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        kind = _kind_for_key(key)
        result[key] = mask_pii(value, kind) if kind is not None else _redact_value(value)
    return result


class JsonFormatter(logging.Formatter):
    """Format a log record as a single redacted JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as one JSON line, masking PII in the message and extras."""
        timestamp = dt.datetime.fromtimestamp(record.created, dt.UTC)
        payload: dict[str, Any] = {
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": _mask_patterns(record.getMessage()),
            "correlation_id": _correlation_provider(),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_")
        }
        payload.update(redact(extras))
        if record.exc_info is not None:
            payload["exception"] = _mask_patterns(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


class StdoutHandler(logging.Handler):
    """Emit formatted records to the *current* ``sys.stdout`` (one line per record)."""

    def emit(self, record: logging.LogRecord) -> None:
        """Write the formatted record, never raising into the caller."""
        try:
            stream = sys.stdout
            stream.write(self.format(record) + "\n")
            stream.flush()
        except Exception:  # pragma: no cover - defensive, per logging contract
            self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    """Return the named logger, configured once with the JSON stdout handler."""
    logger = logging.getLogger(name)
    if not any(isinstance(handler, StdoutHandler) for handler in logger.handlers):
        handler = StdoutHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    return logger
