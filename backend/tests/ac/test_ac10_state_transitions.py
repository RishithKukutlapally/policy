"""AC-10: policy state transitions follow the lifecycle table; everything else is rejected."""

import itertools

import pytest

from src.domain.policy_state_machine import allowed_targets, assert_transition, can_transition
from src.types.enums import PolicyStatus
from src.types.errors import InvalidPolicyStateException

S = PolicyStatus
_NON_TERMINAL = {S.ACTIVE: {S.ENDORSED, S.LAPSED, S.CANCELLED, S.RENEWED}}
_NON_TERMINAL[S.ENDORSED] = set(_NON_TERMINAL[S.ACTIVE])
_ALL_PAIRS = list(itertools.product(PolicyStatus, PolicyStatus))


def _expected(current: PolicyStatus, target: PolicyStatus) -> bool:
    return target in _NON_TERMINAL.get(current, set())


@pytest.mark.ac("AC-10")
def test_ac10_all_25_pairs_are_covered() -> None:
    """AC-10: the parametrisation spans every ordered pair."""
    assert len(_ALL_PAIRS) == 25


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize(("current", "target"), _ALL_PAIRS)
def test_ac10_transition_allowed_or_rejected_per_table(
    current: PolicyStatus, target: PolicyStatus
) -> None:
    """AC-10: each ordered pair is allowed or rejected exactly per the table."""
    expected = _expected(current, target)
    assert can_transition(current, target) is expected
    if expected:
        assert_transition(current, target)
    else:
        with pytest.raises(InvalidPolicyStateException) as exc:
            assert_transition(current, target)
        assert exc.value.code == "INVALID_POLICY_STATE"
        assert exc.value.http_status == 409
        assert isinstance(exc.value.details, dict)
        assert exc.value.details["current"] == current.value
        assert exc.value.details["target"] == target.value


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize("status", [S.LAPSED, S.CANCELLED, S.RENEWED])
def test_ac10_terminal_states_have_no_targets(status: PolicyStatus) -> None:
    """AC-10: terminal statuses allow no transitions."""
    assert allowed_targets(status) == frozenset()
