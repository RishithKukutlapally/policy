"""SQLAlchemy 2 engine, session factory and declarative base.

Services own transactions; repositories receive a ``Session`` and never commit.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model and by Alembic autogenerate."""


def _engine_options(database_url: str) -> dict[str, Any]:
    """Return engine keyword arguments appropriate for the configured backend."""
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}, "future": True}
    return {"future": True}


def create_app_engine(database_url: str | None = None) -> Engine:
    """Create an engine for ``database_url`` (default: the configured one) with FK enforcement."""
    url = database_url or get_settings().database_url
    engine = create_engine(url, **_engine_options(url))
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    """SQLite ships with foreign keys off; turn them on for every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine: Engine = create_app_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def connection_url(connection: Connection) -> str:
    """Return the URL string behind an open connection (used by migration tooling)."""
    return str(connection.engine.url)
