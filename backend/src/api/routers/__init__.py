"""Router registry — every FastAPI router the application mounts.

``/health`` is mounted un-prefixed; every other router is mounted under ``/api`` (AC-21).
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.routers import (
    admin,
    applications,
    cancellations,
    end_of_day,
    endorsements,
    health,
    policies,
    portfolio,
    products,
    quotes,
    renewals,
    underwriting,
)

API_PREFIX = "/api"

#: Routers mounted at the application root (no prefix). Only `/health` may live here.
ROOT_ROUTERS: tuple[APIRouter, ...] = (health.router,)

#: Routers mounted under `API_PREFIX`.
API_ROUTERS: tuple[APIRouter, ...] = (
    admin.router,
    products.router,
    quotes.router,
    applications.router,
    underwriting.router,
    policies.router,
    endorsements.router,
    renewals.router,
    cancellations.router,
    end_of_day.router,
    portfolio.router,
)

__all__ = ["API_PREFIX", "API_ROUTERS", "ROOT_ROUTERS"]
