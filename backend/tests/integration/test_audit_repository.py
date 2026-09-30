"""Integration tests: the append-only ``audit_records`` repository (NFR-02, NFR-04)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from src.repository.audit_repository import AuditRecordRepository
from src.repository.database import Base, create_app_engine
from src.repository.models import AuditAction, AuditEntityType
from src.types.enums import ActorRole

pytestmark = pytest.mark.integration

MUTATING_NAMES = ("update", "delete", "remove", "save", "merge", "set", "upsert")


@pytest.fixture(name="session")
def _session(tmp_path: object) -> Iterator[Session]:
    engine = create_app_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _add(session: Session, entity_id: str, action: AuditAction) -> str:
    repository = AuditRecordRepository(session)
    record = repository.add(
        action=action,
        actor_id="admin-001",
        actor_role=ActorRole.ADMIN,
        entity_type=AuditEntityType.APPLICATION,
        entity_id=entity_id,
        detail={"reason_code": "MO-UW-901"},
        correlation_id="corr-admin-1",
    )
    return record.id


def test_written_record_is_readable(session: Session) -> None:
    """A record added through the repository is readable by id with every field intact."""
    record_id = _add(session, "app-1", AuditAction.UW_OVERRIDE_DECLINE)
    session.commit()

    found = AuditRecordRepository(session).get(record_id)
    assert found is not None
    assert found.actor_id == "admin-001"
    assert found.actor_role == ActorRole.ADMIN.value
    assert found.action == AuditAction.UW_OVERRIDE_DECLINE.value
    assert found.entity_type == AuditEntityType.APPLICATION.value
    assert found.entity_id == "app-1"
    assert found.detail == {"reason_code": "MO-UW-901"}
    assert found.correlation_id == "corr-admin-1"
    assert found.created_at is not None


def test_get_returns_none_for_unknown_id(session: Session) -> None:
    """An unknown record id reads as ``None`` (the caller maps it to 404)."""
    assert AuditRecordRepository(session).get("no-such-id") is None


def test_list_for_entity_returns_records_oldest_first(session: Session) -> None:
    """Two records for the same entity come back in insertion order."""
    first = _add(session, "app-1", AuditAction.UW_APPROVE)
    second = _add(session, "app-1", AuditAction.UW_OVERRIDE_DECLINE)
    _add(session, "app-2", AuditAction.UW_DECLINE)
    session.commit()

    rows = AuditRecordRepository(session).list_for_entity(AuditEntityType.APPLICATION, "app-1")
    assert [row.id for row in rows] == [first, second]
    assert all(row.actor_id == "admin-001" for row in rows)


def test_repository_exposes_no_mutating_method() -> None:
    """NFR-02: the repository is append-only — only ``add`` and read methods are public."""
    public = {name for name in dir(AuditRecordRepository) if not name.startswith("_")}
    assert public == {"add", "get", "list_for_entity"}
    assert not [name for name in public if name.startswith(MUTATING_NAMES)]


def test_repository_does_not_commit(session: Session) -> None:
    """Services own the transaction: ``add`` flushes but never commits."""
    _add(session, "app-9", AuditAction.UW_APPROVE)
    assert session.in_transaction()
    session.rollback()
    rows = AuditRecordRepository(session).list_for_entity(AuditEntityType.APPLICATION, "app-9")
    assert rows == []
