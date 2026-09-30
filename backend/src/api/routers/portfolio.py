"""Admin portfolio dashboard router — contract 2.26 ``GET /api/admin/portfolio`` (AC-20, NFR-04).

ADMIN only: CUSTOMER and UNDERWRITER get 403 ``FORBIDDEN`` and a caller without actor headers gets
401 ``UNAUTHENTICATED`` (both raised in :mod:`src.api.deps`). ``as_of`` is parsed here so a
malformed value answers 422 ``VALIDATION_ERROR`` with detail code ``INVALID_FORMAT`` in the shared
error envelope; it defaults to the business date (DEC-012).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.portfolio import PortfolioResponse
from src.lib.clock import today
from src.service.portfolio_service import PortfolioService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole
from src.types.errors import ValidationError

router = APIRouter(prefix="/admin", tags=["admin"])

AdminActor = Annotated[Actor, Depends(require_role(ActorRole.ADMIN))]
ServiceSession = Annotated[Session, Depends(get_service_session)]


def _as_of(raw: str | None) -> date:
    """Parse the ``as_of`` query value, defaulting to the business date (422 when malformed)."""
    if raw is None or not raw.strip():
        return today()
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        raise ValidationError(
            "Query parameter as_of must be an ISO date (YYYY-MM-DD)",
            [{"field": "as_of", "code": "INVALID_FORMAT"}],
        ) from None


@router.get("/portfolio", summary="Portfolio dashboard as at a business date (ADMIN only)")
def get_portfolio(
    actor: AdminActor, session: ServiceSession, as_of: str | None = None
) -> PortfolioResponse:
    """Contract 2.26 — aggregate the book as at ``as_of`` (default: the business date)."""
    view = PortfolioService(session).portfolio(_as_of(as_of), actor)
    return PortfolioResponse.from_view(view)
