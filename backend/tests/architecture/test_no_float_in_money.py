"""Money is Decimal, never float (NFR-01)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture._ast_utils import SRC, location, parse, py_files

pytestmark = pytest.mark.architecture

MONEY_GLOBS = (
    "domain/premium*.py",
    "domain/refund*.py",
    "domain/endorsement*.py",
    "repository/models/*.py",
)
MONEY_SERVICES = (
    "quote",
    "policy",
    "endorsement",
    "renewal",
    "payment",
    "cancellation",
    "portfolio",
)
FLOAT_TYPES = {"Float", "FLOAT"}


def money_files(src: Path = SRC) -> list[Path]:
    """Money modules that exist right now."""
    found: set[Path] = set()
    for pattern in MONEY_GLOBS:
        found.update(src.glob(pattern))
    return sorted(found)


def float_violations(path: Path) -> list[str]:
    """Any ``float`` name (annotation or call) or float literal in a money module."""
    out: list[str] = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Name) and node.id == "float":
            out.append(f"{location(path, node)} uses `float`")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            out.append(f"{location(path, node)} float literal {node.value!r}")
    return out


def sa_float_violations(path: Path) -> list[str]:
    """``sa.Float`` / ``sqlalchemy.Float`` / bare ``Float`` usage."""
    out: list[str] = []
    for node in ast.walk(parse(path)):
        is_attr = isinstance(node, ast.Attribute) and node.attr in FLOAT_TYPES
        is_name = isinstance(node, ast.Name) and node.id in FLOAT_TYPES
        is_import = isinstance(node, ast.ImportFrom) and any(
            a.name in FLOAT_TYPES for a in node.names
        )
        if is_attr or is_name or is_import:
            out.append(f"{location(path, node)} uses SQLAlchemy Float")
    return out


def test_no_float_in_money_modules() -> None:
    """NFR-01: no float annotation, call or literal in money modules."""
    files = money_files()
    if not files:
        pytest.skip("no money modules (src/domain/premium*, refund*, endorsement*, models.py) yet")
    violations = [v for f in files for v in float_violations(f)]
    assert not violations, "\n".join(violations)


def test_no_sqlalchemy_float_anywhere() -> None:
    """NFR-01: ``sa.Float`` is banned across src/ and migrations/."""
    files = py_files(SRC) + py_files(SRC.parent / "migrations" / "versions")
    violations = [v for f in files for v in sa_float_violations(f)]
    assert not violations, "\n".join(violations)


def test_detector_flags_float_violations(tmp_path: Path) -> None:
    """Negative fixture: the detectors catch annotation, call, literal and sa.Float."""
    bad = tmp_path / "premium_bad.py"
    bad.write_text(
        "import sqlalchemy as sa\npremium: float = 1.5\nx = float('2')\ncol = sa.Float()\n"
    )
    assert len(float_violations(bad)) == 3
    assert len(sa_float_violations(bad)) == 1


def quantize_calls(path: Path) -> list[str]:
    """Any ``.quantize(`` call: rounding belongs to the domain, not to services (CC-009)."""
    return [
        f"{location(path, node)} calls .quantize() outside the domain"
        for node in ast.walk(parse(path))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "quantize"
    ]


def test_money_services_do_not_quantize(src: Path = SRC) -> None:
    """The domain owns rounding: money-handling services never call ``.quantize(``."""
    files = [src / "service" / f"{name}_service.py" for name in MONEY_SERVICES]
    assert all(f.exists() for f in files)
    violations = [v for f in files for v in quantize_calls(f)]
    assert not violations, "\n".join(violations)


def test_quantize_detector_flags_service_rounding(tmp_path: Path) -> None:
    """Negative fixture: re-rounding in a service is caught."""
    bad = tmp_path / "refund_service.py"
    bad.write_text("from decimal import Decimal\nx = Decimal('1').quantize(Decimal('0.01'))\n")
    assert len(quantize_calls(bad)) == 1
