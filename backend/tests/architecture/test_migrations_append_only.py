"""Migrations never destroy append-only tables; one Alembic head (NFR-05)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture._ast_utils import (
    APPEND_ONLY_TABLES,
    MIGRATIONS_VERSIONS,
    calls,
    dotted_name,
    location,
    parse,
    py_files,
)

pytestmark = pytest.mark.architecture

DESTRUCTIVE = {"drop_table", "drop_column", "alter_column"}


def _first_str_arg(call: ast.Call) -> str:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return ""


def _batch_tables(tree: ast.Module) -> dict[int, str]:
    """Map each line inside ``with op.batch_alter_table('t')`` to its table name."""
    spans: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            expr = item.context_expr
            if isinstance(expr, ast.Call) and dotted_name(expr.func).endswith("batch_alter_table"):
                for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                    spans[line] = _first_str_arg(expr)
    return spans


def migration_violations(path: Path) -> list[str]:
    """Destructive ops on append-only tables inside ``upgrade`` (downgrade may reverse creates)."""
    tree = parse(path)
    batch = _batch_tables(tree)
    out: list[str] = []
    for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade"):
        for call in calls(fn):
            name = dotted_name(call.func)
            op = name.rsplit(".", 1)[-1]
            if op not in DESTRUCTIVE:
                continue
            table = _first_str_arg(call) if name.startswith("op.") else batch.get(call.lineno, "")
            if table in APPEND_ONLY_TABLES:
                out.append(f"{location(path, call)} {op} on append-only table {table}")
    return out


def _assignment(node: ast.stmt) -> tuple[str, ast.expr | None]:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    return "", None


def _strings(value: ast.expr | None) -> list[str]:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return [value.value]
    if isinstance(value, ast.Tuple | ast.List):
        return [
            e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
    return []


def find_heads(files: list[Path]) -> list[str]:
    """Revisions that no other revision names as ``down_revision``."""
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in files:
        for node in parse(path).body:
            target, value = _assignment(node)
            if target == "revision":
                revisions.update(_strings(value))
            elif target == "down_revision":
                parents.update(_strings(value))
    return sorted(revisions - parents)


def test_no_destructive_ops_on_append_only_tables() -> None:
    """NFR-05: no drop_table/drop_column/alter_column on append-only tables."""
    files = py_files(MIGRATIONS_VERSIONS)
    if not files:
        pytest.skip("migrations/versions has no revisions yet")
    violations = [v for f in files for v in migration_violations(f)]
    assert not violations, "\n".join(violations)


def test_single_alembic_head() -> None:
    """NFR-05: the revision chain has exactly one head."""
    files = py_files(MIGRATIONS_VERSIONS)
    if not files:
        pytest.skip("migrations/versions has no revisions yet")
    heads = find_heads(files)
    assert len(heads) == 1, f"expected one Alembic head, found {heads}"


def test_detectors_flag_violations(tmp_path: Path) -> None:
    """Negative fixture: destructive ops and two heads are caught."""
    (tmp_path / "a.py").write_text("revision = 'a'\ndown_revision = None\n")
    (tmp_path / "b.py").write_text(
        "revision = 'b'\ndown_revision = 'a'\n"
        "def upgrade():\n    op.drop_table('refunds')\n    op.drop_table('quotes')\n"
        "    with op.batch_alter_table('audit_records') as b:\n        b.drop_column('x')\n"
    )
    (tmp_path / "c.py").write_text("revision = 'c'\ndown_revision = 'a'\n")
    assert len(migration_violations(tmp_path / "b.py")) == 2
    assert find_heads(sorted(tmp_path.glob("*.py"))) == ["b", "c"]
