"""Unit tests for mask_pii / redact edge cases (NFR-03)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.lib import logging as log_module
from src.lib.logging import REDACTED, get_logger, mask_pii, redact

SYNTHETIC_AADHAAR = "999900000001"
SYNTHETIC_PAN = "AAAAA0001A"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (SYNTHETIC_AADHAAR, "XXXX-XXXX-0001"),
        ("9999-0000-0001", "XXXX-XXXX-0001"),
        ("9999 0000 0001", "XXXX-XXXX-0001"),
        ("aadhaar=999900000001 pan=AAAAA0001A", "aadhaar=XXXX-XXXX-0001 pan=XXXXX0001X"),
        ("no pii here", "no pii here"),
        ("", ""),
        ("12345", "12345"),
    ],
)
def test_mask_pii_autodetects_patterns(value: str, expected: str) -> None:
    assert mask_pii(value) == expected


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        (SYNTHETIC_AADHAAR, "aadhaar", "XXXX-XXXX-0001"),
        ("0001", "aadhaar", "XXXX-XXXX-0001"),
        ("12", "aadhaar", REDACTED),
        (None, "aadhaar", REDACTED),
        (SYNTHETIC_PAN, "pan", "XXXXX0001X"),
        ("not-a-pan", "pan", REDACTED),
        ("anything", "health", REDACTED),
        ({"condition": "asthma"}, "health", REDACTED),
        (None, None, REDACTED),
        (12345, None, REDACTED),
    ],
)
def test_mask_pii_with_explicit_kind(value: object, kind: str | None, expected: str) -> None:
    assert mask_pii(value, kind) == expected


def test_redact_masks_known_keys_at_any_depth() -> None:
    payload: dict[str, Any] = {
        "application_id": "app-1",
        "kyc": {
            "full_name": "Test Customer 01",
            "aadhaar_number": SYNTHETIC_AADHAAR,
            "pan": SYNTHETIC_PAN,
            "kyc_document_url": "http://example.test/scan.pdf",
        },
        "applicants": [
            {"health_declaration": {"details": "asthma"}},
            {"medical_notes": "surgery 2019"},
        ],
    }
    result = redact(payload)
    flat = repr(result)
    assert SYNTHETIC_AADHAAR not in flat
    assert SYNTHETIC_PAN not in flat
    assert "asthma" not in flat
    assert "surgery" not in flat
    assert result["application_id"] == "app-1"
    assert result["kyc"]["full_name"] == "Test Customer 01"
    assert result["kyc"]["aadhaar_number"] == "XXXX-XXXX-0001"
    assert result["kyc"]["pan"] == "XXXXX0001X"
    assert result["kyc"]["kyc_document_url"] == REDACTED
    assert result["applicants"][0]["health_declaration"] == REDACTED
    assert result["applicants"][1]["medical_notes"] == REDACTED


def test_redact_keeps_non_pii_values_untouched() -> None:
    payload: dict[str, Any] = {"count": 3, "flag": True, "missing": None, "items": [1, 2]}
    assert redact(payload) == payload


def test_redact_masks_patterns_inside_plain_string_values() -> None:
    assert redact({"note": f"id {SYNTHETIC_AADHAAR}"}) == {"note": "id XXXX-XXXX-0001"}


def test_redact_handles_empty_and_nested_empty_structures() -> None:
    assert redact({}) == {}
    assert redact({"a": {}, "b": []}) == {"a": {}, "b": []}


def test_redact_masks_pii_inside_lists_of_scalars() -> None:
    assert redact({"aadhaar_list": [SYNTHETIC_AADHAAR]}) == {"aadhaar_list": REDACTED}


def test_exception_tracebacks_are_masked(capsys: pytest.CaptureFixture[str]) -> None:
    logger = get_logger("t.exc")
    try:
        raise ValueError(f"leak {SYNTHETIC_AADHAAR}")
    except ValueError:
        logger.exception("failed")
    payload = json.loads(capsys.readouterr().out.strip())
    assert SYNTHETIC_AADHAAR not in payload["exception"]
    assert "XXXX-XXXX-0001" in payload["exception"]


def test_default_correlation_provider_yields_null(capsys: pytest.CaptureFixture[str]) -> None:
    previous = log_module._correlation_provider
    log_module.set_correlation_provider(log_module._no_correlation_id)
    try:
        get_logger("t.nocorr").info("hello")
    finally:
        log_module.set_correlation_provider(previous)
    assert json.loads(capsys.readouterr().out.strip())["correlation_id"] is None
