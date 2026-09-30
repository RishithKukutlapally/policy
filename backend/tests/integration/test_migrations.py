"""Integration tests: Alembic baseline migration on a temp SQLite database."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    env["POLICYFORGE_DATABASE_URL"] = "sqlite:" + "//" + "/" + db_path.as_posix()
    env["DATABASE_URL"] = env["POLICYFORGE_DATABASE_URL"]
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
def test_upgrade_head_succeeds_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "migrations-test.db"

    first = _alembic(["upgrade", "head"], db_path)
    assert first.returncode == 0, first.stderr
    assert db_path.exists()

    second = _alembic(["upgrade", "head"], db_path)
    assert second.returncode == 0, second.stderr


@pytest.mark.integration
def test_exactly_one_head_revision(tmp_path: Path) -> None:
    result = _alembic(["heads"], tmp_path / "heads.db")
    assert result.returncode == 0, result.stderr
    heads = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(heads) == 1, result.stdout


@pytest.mark.integration
def test_baseline_revision_file_exists() -> None:
    versions = BACKEND_ROOT / "migrations" / "versions"
    assert (versions / "0001_baseline.py").exists()
