"""No PII identifier reaches a logging/print call unless masked (NFR-03)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.architecture._ast_utils import SRC, calls, dotted_name, location, parse, py_files

pytestmark = pytest.mark.architecture

PII = re.compile(r"(?<![a-z])(aadhaar|aadhar|pan|health|medical|declaration)(?![a-z])", re.I)
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
MASK = "mask_pii"


def is_log_call(call: ast.Call) -> bool:
    """``print(...)``, ``logging.x(...)`` or ``<...logger|log>.x(...)``."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if isinstance(func, ast.Attribute) and func.attr in LOG_METHODS:
        base = dotted_name(func.value).rsplit(".", 1)[-1].lower()
        return base == "logging" or base.endswith(("logger", "log"))
    return False


def _label(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.keyword):
        return node.arg or ""
    return ""


def _is_mask(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and dotted_name(node.func).rsplit(".", 1)[-1] == MASK


def _pii_names(node: ast.AST) -> list[ast.AST]:
    """PII-named identifiers/keywords/dict keys under ``node``, skipping ``mask_pii(...)``."""
    if _is_mask(node) or (isinstance(node, ast.keyword) and _is_mask(node.value)):
        return []
    hits: list[ast.AST] = []
    if isinstance(node, ast.Dict):
        hits.extend(
            key
            for key in node.keys
            if isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and PII.search(key.value)
        )
    label = _label(node)
    if label and PII.search(label):
        hits.append(node)
    for child in ast.iter_child_nodes(node):
        hits.extend(_pii_names(child))
    return hits


def pii_violations(path: Path) -> list[str]:
    """Locations where a PII identifier appears inside a log/print call."""
    out: list[str] = []
    for call in calls(parse(path)):
        if not is_log_call(call):
            continue
        for part in [*call.args, *call.keywords]:
            out.extend(f"{location(path, n)} PII in log call" for n in _pii_names(part))
    return out


def test_no_pii_in_log_calls() -> None:
    """NFR-03: Aadhaar/PAN/health identifiers must be wrapped in mask_pii()."""
    files = py_files(SRC)
    assert files, "src/ must contain modules"
    violations = [v for f in files for v in pii_violations(f)]
    assert not violations, "\n".join(violations)


def test_detector_flags_pii_and_allows_masked(tmp_path: Path) -> None:
    """Negative fixture: raw PII is caught; mask_pii()-wrapped and non-PII names are not."""
    bad = tmp_path / "svc.py"
    bad.write_text(
        "logger.info(f'x {aadhaar}')\n"
        "print(pan_number)\n"
        "logger.warning('m', extra={'health': 1})\n"
        "logger.info('ok', aadhaar=mask_pii(aadhaar))\n"
        "logger.info('panel %s', panel)\n"
    )
    assert len(pii_violations(bad)) == 3
