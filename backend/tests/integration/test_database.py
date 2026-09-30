"""Integration tests for the engine / session factory."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.repository.database import (
    Base,
    SessionLocal,
    _engine_options,
    connection_url,
    create_app_engine,
    get_session,
)


def _sqlite_url(db_path: Path) -> str:
    return "sqlite:" + "//" + "/" + db_path.as_posix()


@pytest.mark.integration
def test_engine_enables_sqlite_foreign_keys(tmp_path: Path) -> None:
    engine = create_app_engine(_sqlite_url(tmp_path / "fk.db"))
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection_url(connection).startswith("sqlite")
    engine.dispose()


def test_engine_options_differ_by_backend() -> None:
    assert "connect_args" in _engine_options("sqlite:" + "///:memory:")
    assert "connect_args" not in _engine_options("postgresql+psycopg://host/db")


@pytest.mark.integration
def test_get_session_yields_and_closes_a_session() -> None:
    generator = get_session()
    session = next(generator)
    assert isinstance(session, Session)
    with pytest.raises(StopIteration):
        next(generator)


def test_session_factory_and_base_are_configured() -> None:
    assert SessionLocal.kw["autoflush"] is False
    assert Base.metadata is not None
