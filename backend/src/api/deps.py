"""API-layer auth stub and shared FastAPI dependencies (NFR-04, AC-22).

The auth stub is documented, not real: the caller declares itself with ``X-Actor-Id`` and
``X-Actor-Role``. There is no IdP, no token and no session
(`specs/design/api-contracts.md` §0.2, §0.6).

Check order: headers missing/blank or role unknown -> 401 ``UNAUTHENTICATED``; role not allowed on
the route -> 403 ``FORBIDDEN``. ``SYSTEM`` is internal to the scheduler and is never accepted from a
header (DEC-010). Role checks live only here — no service or domain module sees a header.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Depends, Header

from src.types.enums import ActorRole
from src.types.errors import ForbiddenError, UnauthenticatedError

ACTOR_ID_HEADER: Final = "X-Actor-Id"
ACTOR_ROLE_HEADER: Final = "X-Actor-Role"

#: Roles a client may present in ``X-Actor-Role``; `ActorRole.SYSTEM` is excluded (DEC-010).
HEADER_ROLES: Final[frozenset[ActorRole]] = frozenset(
    {ActorRole.CUSTOMER, ActorRole.UNDERWRITER, ActorRole.ADMIN}
)


@dataclass(frozen=True, slots=True)
class Actor:
    """The authenticated caller: an opaque actor id and the role it acts in."""

    actor_id: str
    role: ActorRole

    @property
    def id(self) -> str:
        """Alias of :attr:`actor_id` for call sites that read ``actor.id``."""
        return self.actor_id


def _require_header(value: str | None, name: str) -> str:
    """Return the trimmed header value, or raise 401 when it is missing or blank."""
    trimmed = (value or "").strip()
    if not trimmed:
        raise UnauthenticatedError(f"Header {name} is required")
    return trimmed


def _parse_role(raw: str) -> ActorRole:
    """Map a header value onto an acceptable role, or raise 401."""
    try:
        role = ActorRole(raw)
    except ValueError:
        raise UnauthenticatedError(f"Header {ACTOR_ROLE_HEADER} is not a known role") from None
    if role not in HEADER_ROLES:
        raise UnauthenticatedError(f"Role {role.value} is not accepted from {ACTOR_ROLE_HEADER}")
    return role


def get_current_actor(
    x_actor_id: Annotated[str | None, Header(alias=ACTOR_ID_HEADER)] = None,
    x_actor_role: Annotated[str | None, Header(alias=ACTOR_ROLE_HEADER)] = None,
) -> Actor:
    """Resolve the calling :class:`Actor` from the actor headers (401 when unusable)."""
    actor_id = _require_header(x_actor_id, ACTOR_ID_HEADER)
    raw_role = _require_header(x_actor_role, ACTOR_ROLE_HEADER)
    return Actor(actor_id=actor_id, role=_parse_role(raw_role))


CurrentActor = Annotated[Actor, Depends(get_current_actor)]


def require_role(*roles: ActorRole) -> Callable[[Actor], Actor]:
    """Build a dependency that admits ``roles`` only and raises 403 ``FORBIDDEN`` otherwise."""
    allowed = frozenset(roles)

    def dependency(actor: CurrentActor) -> Actor:
        """Return the actor when its role is allowed on this route."""
        if actor.role not in allowed:
            raise ForbiddenError(f"Role {actor.role.value} is not allowed on this route")
        return actor

    return dependency
