"""Append-only repositories expose ``add`` + reads only (NFR-02, NFR-05)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.architecture._ast_utils import (
    APPEND_ONLY_STEMS,
    SRC,
    calls,
    dotted_name,
    location,
    parse,
    py_files,
)

pytestmark = pytest.mark.architecture

FORBIDDEN_METHOD = re.compile(r"^(update|delete|remove|set|upsert|merge)")
FORBIDDEN_CALLS = {"update", "delete"}


def is_append_only_class(name: str) -> bool:
    """Repository class for one of the append-only models."""
    return any(stem in name for stem in APPEND_ONLY_STEMS)


def repo_violations(path: Path) -> list[str]:
    """Mutating public methods or SQLAlchemy update/delete calls in append-only repositories."""
    out: list[str] = []
    for cls in (n for n in ast.walk(parse(path)) if isinstance(n, ast.ClassDef)):
        if not is_append_only_class(cls.name):
            continue
        for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)):
            if not fn.name.startswith("_") and FORBIDDEN_METHOD.match(fn.name):
                out.append(f"{location(path, fn)} {cls.name}.{fn.name} is a mutating method")
        for call in calls(cls):
            name = dotted_name(call.func).rsplit(".", 1)[-1]
            if name in FORBIDDEN_CALLS:
                out.append(f"{location(path, call)} {cls.name} calls `{name}(`")
    return out


def test_append_only_repositories_have_no_mutators() -> None:
    """NFR-02: no update/delete/remove/set method and no update(/delete( call."""
    files = py_files(SRC / "repository")
    if not any(f.name != "__init__.py" and f.name != "database.py" for f in files):
        pytest.skip("src/repository has no append-only repositories yet")
    violations = [v for f in files for v in repo_violations(f)]
    assert not violations, "\n".join(violations)


def test_detector_flags_mutators(tmp_path: Path) -> None:
    """Negative fixture: mutating method and delete()/update() calls are caught."""
    bad = tmp_path / "audit_repo.py"
    bad.write_text(
        "class AuditRecordRepository:\n"
        "    def add(self, r): ...\n"
        "    def delete(self, id):\n"
        "        self.session.delete(id)\n"
        "    def touch(self):\n"
        "        return update(X)\n"
        "class QuoteRepository:\n"
        "    def update(self): ...\n"
    )
    found = repo_violations(bad)
    assert len(found) == 3
    assert not any("QuoteRepository" in v for v in found)
