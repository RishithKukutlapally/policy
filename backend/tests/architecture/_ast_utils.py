"""Shared AST helpers for the architecture tests (no app start-up, no imports of ``src``)."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SRC = BACKEND / "src"
MIGRATIONS_VERSIONS = BACKEND / "migrations" / "versions"

# Append-only model stems and tables (docs/conventions.md -> "Persistence", NFR-02/05).
APPEND_ONLY_STEMS = (
    "RuleSetVersion",
    "UnderwritingDecision",
    "UnderwritingOverride",
    "PolicyStateTransition",
    "Endorsement",
    "PremiumPayment",
    "Refund",
    "AuditRecord",
)
APPEND_ONLY_TABLES = frozenset(
    {
        "rule_set_versions",
        "underwriting_decisions",
        "underwriting_overrides",
        "policy_state_transitions",
        "endorsements",
        "premium_payments",
        "refunds",
        "audit_records",
    }
)


def py_files(root: Path) -> list[Path]:
    """Return every ``*.py`` file under ``root`` (sorted); empty when ``root`` is missing."""
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def parse(path: Path) -> ast.Module:
    """Parse a source file into an AST."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def dotted_name(node: ast.AST) -> str:
    """Render ``a.b.c`` for Name/Attribute chains; empty string for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def calls(tree: ast.AST) -> Iterator[ast.Call]:
    """Yield every call expression in ``tree``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def location(path: Path, node: ast.AST, base: Path = BACKEND) -> str:
    """``relative/path.py:line`` for violation messages."""
    try:
        shown = path.relative_to(base).as_posix()
    except ValueError:
        shown = path.as_posix()
    return f"{shown}:{getattr(node, 'lineno', 0)}"
