"""Transaction boundary for the service layer (`docs/conventions.md` -> Backend modules).

Services own their transaction and commit exactly once; the API layer only asks for a session.
It lives here rather than in `src/api/` because `src.api` may not import `src.repository`
(import-linter contract "API goes through services").
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.repository.database import SessionLocal


def get_service_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def unit_of_work() -> Iterator[Session]:
    """Run a block in one transaction: commit on success, roll back on any error (AC-06)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
