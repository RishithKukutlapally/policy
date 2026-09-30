"""Layer direction and domain purity via import-linter (NFR-08, E1-S4 AC-1)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.architecture._ast_utils import BACKEND

pytestmark = pytest.mark.architecture

_RUN = "import sys; from importlinter.cli import lint_imports_command as c; sys.exit(c())"


def run_lint_imports() -> subprocess.CompletedProcess[str]:
    """Run ``lint-imports`` from the backend directory."""
    return subprocess.run(
        [sys.executable, "-c", _RUN],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_all_import_contracts_kept() -> None:
    """NFR-08: every import-linter contract is KEPT and none is broken."""
    result = run_lint_imports()
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "0 broken" in output, output
    assert "BROKEN" not in output, output
