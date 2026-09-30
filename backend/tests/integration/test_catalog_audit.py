"""Catalog mutations are audited exactly once and never rewrite history (NFR-02, NFR-04)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.repository.models import AuditAction, AuditEntityType, AuditRecord, RuleSetVersion
from src.service.catalog_service import CatalogService
from src.types.enums import ActorRole, ProductCode
from src.types.errors import VersionImmutableError
from tests.conftest import rule_body

pytestmark = pytest.mark.integration

MOTOR = ProductCode.MOTOR.value
ENTITY_ID = "MOTOR:v2"


class _Actor:
    """Structural stand-in for the API layer's `Actor`."""

    def __init__(self, actor_id: str = "admin-001", role: ActorRole = ActorRole.ADMIN) -> None:
        self.actor_id = actor_id
        self.role = role


def _audit(session: Session) -> list[AuditRecord]:
    statement = select(AuditRecord).order_by(AuditRecord.created_at, AuditRecord.action)
    return list(session.execute(statement).scalars())


def _rows(session: Session) -> list[RuleSetVersion]:
    statement = select(RuleSetVersion).order_by(RuleSetVersion.version, RuleSetVersion.revision)
    return list(session.execute(statement).scalars())


def test_each_mutating_use_case_writes_exactly_one_audit_row(seeded_session: Session) -> None:
    service = CatalogService(seeded_session)
    actor = _Actor()
    service.create_draft(MOTOR, rule_body(), actor)
    service.replace_draft(MOTOR, 2, rule_body(base_rate="0.0330"), actor)
    service.publish(MOTOR, 2, actor)
    records = _audit(seeded_session)
    assert [r.action for r in records] == [
        AuditAction.RULE_VERSION_DRAFT_CREATED.value,
        AuditAction.RULE_VERSION_DRAFT_REPLACED.value,
        AuditAction.RULE_VERSION_PUBLISHED.value,
    ]
    assert {r.actor_id for r in records} == {"admin-001"}
    assert {r.actor_role for r in records} == {ActorRole.ADMIN.value}
    assert {r.entity_type for r in records} == {AuditEntityType.RULE_SET_VERSION.value}
    assert {r.entity_id for r in records} == {ENTITY_ID}


def test_audit_detail_carries_only_opaque_version_metadata(seeded_session: Session) -> None:
    service = CatalogService(seeded_session)
    service.create_draft(MOTOR, rule_body(), _Actor())
    detail = _audit(seeded_session)[0].detail
    assert detail is not None
    assert set(detail) == {"product", "version", "revision", "status", "content_sha256"}
    assert detail["version"] == 2
    assert len(str(detail["content_sha256"])) == 64


def test_a_rejected_mutation_writes_neither_a_version_row_nor_an_audit_row(
    seeded_session: Session,
) -> None:
    service = CatalogService(seeded_session)
    with pytest.raises(VersionImmutableError):
        service.replace_draft(MOTOR, 1, rule_body(), _Actor())
    assert len(_rows(seeded_session)) == 3
    assert _audit(seeded_session) == []


def test_history_is_append_only_across_the_whole_lifecycle(seeded_session: Session) -> None:
    service = CatalogService(seeded_session)
    actor = _Actor()
    before = {(row.id, row.content_sha256, row.status) for row in _rows(seeded_session)}
    service.create_draft(MOTOR, rule_body(), actor)
    service.replace_draft(MOTOR, 2, rule_body(base_rate="0.0330"), actor)
    service.publish(MOTOR, 2, actor)
    after = _rows(seeded_session)
    assert before <= {(row.id, row.content_sha256, row.status) for row in after}
    motor = [row for row in after if row.product == MOTOR]
    assert [(row.version, row.revision, row.status) for row in motor] == [
        (1, 1, "PUBLISHED"),
        (2, 1, "DRAFT"),
        (2, 2, "DRAFT"),
        (2, 3, "PUBLISHED"),
    ]
    total = seeded_session.execute(select(func.count()).select_from(RuleSetVersion)).scalar_one()
    assert total == 6
