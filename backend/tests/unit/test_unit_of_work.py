"""The service layer's transaction boundary: one commit on success, rollback on failure (AC-06)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository import database
from src.repository.database import Base, create_app_engine
from src.repository.models import AuditAction, AuditEntityType, AuditRecord
from src.service.audit_service import AuditService
from src.service.unit_of_work import get_service_session, unit_of_work
from src.types.enums import ActorRole


@pytest.fixture(name="bound_engine")
def _bound_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """Point ``SessionLocal`` at a temp database for the duration of one test."""
    engine = create_app_engine("sqlite:///" + (tmp_path / "uow.db").as_posix())
    Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", lambda: Session(engine))
    monkeypatch.setattr("src.service.unit_of_work.SessionLocal", lambda: Session(engine))
    yield engine
    engine.dispose()


def _record(session: Session) -> None:
    AuditService(session).record(
        action=AuditAction.RULE_VERSION_PUBLISHED,
        actor_id="admin-001",
        actor_role=ActorRole.ADMIN,
        entity_type=AuditEntityType.RULE_SET_VERSION,
        entity_id="MOTOR:v1",
    )


def _count(engine: Engine) -> int:
    with Session(engine) as session:
        return int(session.execute(select(func.count()).select_from(AuditRecord)).scalar_one())


def test_unit_of_work_commits_on_success(bound_engine: Engine) -> None:
    with unit_of_work() as session:
        _record(session)
    assert _count(bound_engine) == 1


def test_unit_of_work_rolls_back_on_failure(bound_engine: Engine) -> None:
    with pytest.raises(RuntimeError), unit_of_work() as session:
        _record(session)
        raise RuntimeError("boom")
    assert _count(bound_engine) == 0


def test_get_service_session_yields_and_closes_a_session(bound_engine: Engine) -> None:
    sessions = list(get_service_session())
    assert len(sessions) == 1
    generator = get_service_session()
    session = next(generator)
    assert session.is_active
    with pytest.raises(StopIteration):
        next(generator)
