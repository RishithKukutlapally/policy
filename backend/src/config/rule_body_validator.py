"""Validation of an **incoming** rule-set body against the rule-file schema (AC-11, DEC-009).

`rule_loader` reads rule *files* from disk; this module validates a rule body that arrived over the
API before it becomes a ``rule_set_versions`` row. It normalises the server-assigned
``product``/``version``/``status``, rejects a body that contradicts them, re-codes schema failures
on money leaves as ``MONEY_MUST_BE_STRING`` (contract §0.4) and checks the cross-field eligibility
bound. Failures raise :class:`~src.config.rule_loader.RuleFileValidationError` (422
``VALIDATION_ERROR``) with one ``details`` entry per offending dotted field path.
"""

from __future__ import annotations

import hashlib
import json
import numbers
from collections.abc import Mapping, Sequence
from typing import Any, Final

from src.config.rule_loader import RuleFileValidationError, build_rule_set
from src.types.enums import ProductCode, RuleSetStatus

#: Rule-file leaves that must be JSON strings so they load as `Decimal` (NFR-01).
MONEY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "base_rate",
        "minimum_premium",
        "min_sum_insured",
        "max_sum_insured",
        "admin_fee",
        "multiplier",
    }
)


def canonical_json(document: Mapping[str, Any]) -> str:
    """Stable JSON rendering of a rule body, used for its content hash."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_sha256(document: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical JSON body, mirroring `PUBLISHED.lock` (NFR-05)."""
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def _value_at(document: Mapping[str, Any], path: str) -> Any:
    """Resolve a dotted JSON path inside ``document``, or ``None`` when it does not exist."""
    node: Any = document
    for part in path.split("."):
        if isinstance(node, Mapping) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def _is_number(value: Any) -> bool:
    """True for a JSON number (never for a bool, which is a valid JSON value elsewhere)."""
    return isinstance(value, numbers.Number) and not isinstance(value, bool)


def _refined_details(
    document: Mapping[str, Any], details: Sequence[Mapping[str, str]]
) -> list[dict[str, str]]:
    """Re-code schema failures on money leaves as ``MONEY_MUST_BE_STRING`` (contract §0.4)."""
    refined: list[dict[str, str]] = []
    for detail in details:
        field = detail.get("field", "<root>")
        money = field.rsplit(".", 1)[-1] in MONEY_FIELDS and _is_number(_value_at(document, field))
        refined.append(
            {"field": field, "code": "MONEY_MUST_BE_STRING" if money else detail["code"]}
        )
    return refined


def _declared_field_issues(
    body: Mapping[str, Any], product: ProductCode, version: int, status: RuleSetStatus
) -> list[dict[str, str]]:
    """Reject a body whose own ``product``/``version``/``status`` contradict the target."""
    issues: list[dict[str, str]] = []
    if body.get("product") not in (None, product.value):
        issues.append({"field": "product", "code": "INVALID_FORMAT"})
    if body.get("version") not in (None, version):
        issues.append({"field": "version", "code": "OUT_OF_RANGE"})
    if body.get("status") not in (None, status.value):
        issues.append({"field": "status", "code": "INVALID_FORMAT"})
    return issues


def _eligibility_issues(document: Mapping[str, Any]) -> list[dict[str, str]]:
    """``eligibility.min_age`` may not exceed ``max_age`` (contract §2.4)."""
    eligibility = document.get("eligibility")
    if not isinstance(eligibility, Mapping):
        return []
    if int(eligibility["min_age"]) > int(eligibility["max_age"]):
        return [{"field": "eligibility.min_age", "code": "OUT_OF_RANGE"}]
    return []


def validated_rule_document(
    body: Mapping[str, Any],
    product: ProductCode,
    version: int,
    status: RuleSetStatus,
    *,
    check_declared_fields: bool = True,
) -> dict[str, Any]:
    """Return the body to store, or raise ``RuleFileValidationError`` with per-field details."""
    label = f"{product.value} v{version}"
    if check_declared_fields:
        issues = _declared_field_issues(body, product, version, status)
        if issues:
            raise RuleFileValidationError(f"{label} body contradicts the target version", issues)
    document = {**dict(body), "product": product.value, "version": version, "status": status.value}
    try:
        build_rule_set(document, label=label)
    except RuleFileValidationError as exc:
        details = exc.details if isinstance(exc.details, list) else []
        raise RuleFileValidationError(exc.message, _refined_details(document, details)) from None
    issues = _eligibility_issues(document)
    if issues:
        raise RuleFileValidationError(f"{label} eligibility bounds are inconsistent", issues)
    return document
