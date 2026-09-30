"""FastAPI application entry point (``src.main:app``)."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.errors import register_exception_handlers
from src.api.middleware import CorrelationIdMiddleware
from src.api.routers import API_PREFIX, API_ROUTERS, ROOT_ROUTERS

APP_TITLE = "PolicyForge API"
APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    """Build the FastAPI application: routers plus the canonical error handlers."""
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        summary="Policy issuance and lifecycle management for Horizon Insurance.",
    )
    app.add_middleware(CorrelationIdMiddleware)
    for router in ROOT_ROUTERS:
        app.include_router(router)
    for router in API_ROUTERS:
        app.include_router(router, prefix=API_PREFIX)
    register_exception_handlers(app)
    return app


app = create_app()
