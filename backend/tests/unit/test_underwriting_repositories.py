"""AC-09 / NFR-02: append-only surface of the underwriting repositories."""

from __future__ import annotations

import pytest

from src.repository.application_repository import ApplicationRepository
from src.repository.underwriting_repository import (
    UnderwritingDecisionRepository,
    UnderwritingOverrideRepository,
)

_MUTATORS = ("update", "delete", "remove", "set", "upsert", "merge")


def _public(cls: type) -> set[str]:
    return {name for name in dir(cls) if not name.startswith("_")}


@pytest.mark.ac("AC-09")
@pytest.mark.parametrize(
    "repository", [UnderwritingDecisionRepository, UnderwritingOverrideRepository]
)
def test_ac09_append_only_repositories_expose_add_and_reads_only(repository: type) -> None:
    """AC-09: only `add` plus read methods; nothing that starts like a mutator."""
    names = _public(repository)
    assert "add" in names
    assert not [n for n in names if n.startswith(_MUTATORS)]


@pytest.mark.ac("AC-03")
def test_ac03_application_repository_exposes_no_delete() -> None:
    """AC-03: the status projection repository can add, read and transition but never delete."""
    names = _public(ApplicationRepository)
    assert {"add", "get", "transition"} <= names
    assert not [n for n in names if n.startswith(("delete", "remove"))]
