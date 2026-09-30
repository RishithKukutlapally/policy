"""PUBLISHED.lock is a faithful sha256 ledger of every PUBLISHED rule file (AC-02, NFR-05)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

POLICY_RULES = Path(__file__).resolve().parents[2] / "policy_rules"
LOCK_PATH = POLICY_RULES / "PUBLISHED.lock"
EXPECTED_PATHS = {"term_life/v1.json", "motor/v1.json", "household/v1.json"}


def _lock_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in LOCK_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative_path = line.split("  ", 1)
        entries[relative_path] = digest
    return entries


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _published_files() -> set[str]:
    published: set[str] = set()
    for path in POLICY_RULES.glob("*/v*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "PUBLISHED":
            published.add(path.relative_to(POLICY_RULES).as_posix())
    return published


@pytest.mark.ac("AC-02")
def test_ac02_lock_lists_exactly_the_three_v1_files() -> None:
    assert set(_lock_entries()) == EXPECTED_PATHS


@pytest.mark.ac("AC-02")
def test_ac02_lock_lines_are_sorted_by_path() -> None:
    paths = [line.split("  ", 1)[1] for line in LOCK_PATH.read_text(encoding="utf-8").splitlines()]
    assert paths == sorted(paths)


@pytest.mark.ac("AC-02")
def test_ac02_every_lock_hash_matches_the_file() -> None:
    for relative_path, digest in _lock_entries().items():
        assert digest == _sha256(POLICY_RULES / relative_path), relative_path


@pytest.mark.ac("AC-02")
def test_ac02_every_published_file_is_in_the_lock() -> None:
    assert _published_files() == set(_lock_entries())
