"""Unit tests for the pure policy state machine."""

import pytest

from src.domain import policy_state_machine as psm
from src.types.enums import PolicyStatus

S = PolicyStatus


def test_allowed_targets_active_and_endorsed() -> None:
    both = frozenset({S.ENDORSED, S.LAPSED, S.CANCELLED, S.RENEWED})
    assert psm.allowed_targets(S.ACTIVE) == both
    assert psm.allowed_targets(S.ENDORSED) == both


@pytest.mark.parametrize(
    ("status", "terminal"),
    [
        (S.ACTIVE, False),
        (S.ENDORSED, False),
        (S.LAPSED, True),
        (S.CANCELLED, True),
        (S.RENEWED, True),
    ],
)
def test_is_terminal(status: PolicyStatus, terminal: bool) -> None:
    assert psm.is_terminal(status) is terminal


def test_transition_table_is_immutable() -> None:
    table = psm.TRANSITIONS
    with pytest.raises(TypeError):
        table[S.LAPSED] = frozenset({S.ACTIVE})  # type: ignore[index]
    with pytest.raises(AttributeError):
        psm.allowed_targets(S.ACTIVE).add(S.ACTIVE)  # type: ignore[attr-defined]
