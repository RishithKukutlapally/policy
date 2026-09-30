"""Shared ownership guard: a CUSTOMER sees only their own policies; anything else is a 404."""

from __future__ import annotations

from src.repository.models import Policy
from src.repository.policy_repository import PolicyRepository
from src.service.quote_service import ActingActor
from src.types.enums import ActorRole
from src.types.errors import NotFoundError


def owned_policy(policies: PolicyRepository, policy_number: str, actor: ActingActor) -> Policy:
    """The policy, or 404 when unknown or (for a CUSTOMER) owned by someone else."""
    policy = policies.get_by_number(policy_number)
    if policy is None or (
        actor.role is ActorRole.CUSTOMER and policy.customer_id != actor.actor_id
    ):
        raise NotFoundError("Policy not found")
    return policy
