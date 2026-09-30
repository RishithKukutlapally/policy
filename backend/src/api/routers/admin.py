"""Admin router.

Currently holds **only the auth-boundary probe** ``GET /api/admin/ping``: the smallest possible
ADMIN-protected route, so AC-22 (401/403/200 behaviour of the role-header stub) is testable end to
end before the real admin endpoints (`POST /api/admin/end-of-day`, `GET /api/admin/portfolio`) land.
Remove the probe when those endpoints exist.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.deps import Actor, require_role
from src.types.enums import ActorRole

router = APIRouter(prefix="/admin", tags=["admin"])

AdminActor = Annotated[Actor, Depends(require_role(ActorRole.ADMIN))]


@router.get("/ping", summary="Auth-boundary probe (ADMIN only)")
def admin_ping(actor: AdminActor) -> dict[str, str]:
    """Echo the resolved actor so the auth stub is observable (AC-22)."""
    return {"status": "ok", "actor_id": actor.actor_id, "actor_role": actor.role.value}
