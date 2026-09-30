"""Liveness endpoint — the only route without the ``/api`` prefix (AC-21)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Body of ``GET /health``."""

    status: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def get_health() -> HealthResponse:
    """Return ``{"status": "ok"}``; does no database work and requires no auth (NFR-07)."""
    return HealthResponse(status="ok")
