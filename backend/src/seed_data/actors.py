"""The demo actors the seed acts as (``docs/conventions.md`` -> "API / auth stub").

The services accept any structural ``ActingActor``; :class:`SeedActor` is that shape, so the seed
never has to import :mod:`src.api`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from src.types.enums import ActorRole

#: Identity of the end-of-day scheduler (DEC-010) — never accepted from a request header.
SYSTEM_ACTOR_ID: Final = "system-eod"
#: The demo underwriter and admin shown in the README quick start.
UNDERWRITER_ACTOR_ID: Final = "uw-001"
ADMIN_ACTOR_ID: Final = "admin-001"
#: ``cust-001`` owns the whole lifecycle showcase so the customer UI is never empty.
PRIMARY_CUSTOMER_ID: Final = "cust-001"


@dataclass(frozen=True, slots=True)
class SeedActor:
    """An ``ActingActor`` the seed passes to the services."""

    actor_id: str
    role: ActorRole


def customer(index: int) -> SeedActor:
    """The ``cust-0NN`` demo customer with the 1-based ``index``."""
    return SeedActor(f"cust-{index:03d}", ActorRole.CUSTOMER)


def underwriter() -> SeedActor:
    """The demo underwriter ``uw-001``."""
    return SeedActor(UNDERWRITER_ACTOR_ID, ActorRole.UNDERWRITER)


def admin() -> SeedActor:
    """The demo administrator ``admin-001``."""
    return SeedActor(ADMIN_ACTOR_ID, ActorRole.ADMIN)


def system() -> SeedActor:
    """The scheduler identity used by the seeded end-of-day run."""
    return SeedActor(SYSTEM_ACTOR_ID, ActorRole.SYSTEM)
