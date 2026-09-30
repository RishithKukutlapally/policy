"""'Today' is read only through ``src/lib/clock.py`` (DEC-012, E1-S4 AC-6)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture._ast_utils import SRC, calls, dotted_name, location, parse, py_files

pytestmark = pytest.mark.architecture

CLOCK = SRC / "lib" / "clock.py"
CLOCK_METHODS = {"today", "now", "utcnow"}


def clock_violations(path: Path) -> list[str]:
    """Calls to ``date.today()``, ``datetime.now()/utcnow()/today()`` (any import alias path)."""
    out: list[str] = []
    for call in calls(parse(path)):
        func = call.func
        if not (isinstance(func, ast.Attribute) and func.attr in CLOCK_METHODS):
            continue
        owner = dotted_name(func.value).rsplit(".", 1)[-1]
        if owner in {"date", "datetime"}:
            out.append(f"{location(path, call)} calls {owner}.{func.attr}()")
    return out


def test_today_only_read_from_clock() -> None:
    """DEC-012: no module except src/lib/clock.py reads the wall clock."""
    files = [f for f in py_files(SRC) if f != CLOCK]
    violations = [v for f in files for v in clock_violations(f)]
    assert not violations, "\n".join(violations)


def test_detector_flags_wall_clock_calls(tmp_path: Path) -> None:
    """Negative fixture: date.today() and dt.datetime.now() are caught."""
    bad = tmp_path / "svc.py"
    bad.write_text(
        "import datetime as dt\nfrom datetime import date\n"
        "a = date.today()\nb = dt.datetime.now()\nc = dt.date.today()\nd = other.now()\n"
    )
    assert len(clock_violations(bad)) == 3
