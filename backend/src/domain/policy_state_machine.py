"""Pure policy lifecycle state machine (AC-10); table mirrors docs/conventions.md."""

from collections.abc import Mapping
from types import MappingProxyType

from src.types.enums import PolicyStatus
from src.types.errors import InvalidPolicyStateException

_LIVE_TARGETS: frozenset[PolicyStatus] = frozenset(
    {
        PolicyStatus.ENDORSED,
        PolicyStatus.LAPSED,
        PolicyStatus.CANCELLED,
        PolicyStatus.RENEWED,
    }
)

TRANSITIONS: Mapping[PolicyStatus, frozenset[PolicyStatus]] = MappingProxyType(
    {
        PolicyStatus.ACTIVE: _LIVE_TARGETS,
        PolicyStatus.ENDORSED: _LIVE_TARGETS,
        PolicyStatus.LAPSED: frozenset(),
        PolicyStatus.CANCELLED: frozenset(),
        PolicyStatus.RENEWED: frozenset(),
    }
)


def allowed_targets(current: PolicyStatus) -> frozenset[PolicyStatus]:
    """Return the statuses reachable from `current` (empty for terminal states)."""
    return TRANSITIONS[current]


def can_transition(current: PolicyStatus, target: PolicyStatus) -> bool:
    """Whether `current -> target` is allowed."""
    return target in TRANSITIONS[current]


def is_terminal(status: PolicyStatus) -> bool:
    """Whether the status has no outgoing transitions."""
    return not TRANSITIONS[status]


def assert_transition(current: PolicyStatus, target: PolicyStatus) -> None:
    """Raise `InvalidPolicyStateException` (409) unless `current -> target` is allowed."""
    if not can_transition(current, target):
        raise InvalidPolicyStateException(
            f"Cannot transition policy from {current.value} to {target.value}",
            {"current": current.value, "target": target.value},
        )
