"""The lifecycle repositories are append-only (NFR-02, E5-S2 AC-5)."""

from __future__ import annotations

import pytest

from src.repository.policy_lifecycle_repository import (
    EndorsementRepository,
    PolicyLifecycleRepository,
    PolicyStateTransitionRepository,
    PremiumPaymentRepository,
    RefundRepository,
)
from src.repository.policy_repository import PolicyRepository

APPEND_ONLY = (
    PolicyStateTransitionRepository,
    EndorsementRepository,
    PremiumPaymentRepository,
    RefundRepository,
    PolicyLifecycleRepository,
)

_FORBIDDEN = ("update", "delete", "remove", "merge", "upsert")


@pytest.mark.parametrize("repository", APPEND_ONLY)
def test_append_only_repositories_expose_no_mutator(repository: type) -> None:
    """No public attribute of an append-only repository mentions update/delete/remove."""
    public = [name for name in dir(repository) if not name.startswith("_")]
    assert public, repository
    offenders = [n for n in public if any(word in n.lower() for word in _FORBIDDEN)]
    assert offenders == []


def test_transition_repository_public_surface_is_add_and_reads() -> None:
    """AC-5: ``add`` plus read methods only."""
    public = sorted(n for n in dir(PolicyStateTransitionRepository) if not n.startswith("_"))
    assert public == ["add", "list_for_policy"]


def test_policy_projection_repository_keeps_its_update_projection() -> None:
    """`policies` is a projection, so it may move status — but it has no delete."""
    public = [n for n in dir(PolicyRepository) if not n.startswith("_")]
    assert "update_projection" in public
    assert not [n for n in public if "delete" in n or "remove" in n]
