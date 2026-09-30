"""Unit tests for the audit recording helper (NFR-03, NFR-04)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.lib.correlation import reset_correlation_id, set_correlation_id
from src.repository.database import Base, create_app_engine
from src.repository.models import AuditAction, AuditEntityType
from src.service.audit_service import AuditService
from src.types.enums import ActorRole


@pytest.fixture(name="session")
def _session() -> Iterator[Session]:
    engine = create_app_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_records_the_action_actor_and_entity(session: Session) -> None:
    """The recorded row carries the action, the acting actor and the target entity."""
    record = AuditService(session).record(
        action=AuditAction.RULE_VERSION_PUBLISHED,
        actor_id="admin-001",
        actor_role=ActorRole.ADMIN,
        entity_type=AuditEntityType.RULE_SET_VERSION,
        entity_id="MOTOR/v1",
        detail={"product": "MOTOR", "version": 1},
    )
    assert record.action == AuditAction.RULE_VERSION_PUBLISHED.value
    assert record.actor_id == "admin-001"
    assert record.actor_role == ActorRole.ADMIN.value
    assert record.entity_type == AuditEntityType.RULE_SET_VERSION.value
    assert record.entity_id == "MOTOR/v1"
    assert record.detail == {"product": "MOTOR", "version": 1}


def test_records_the_system_actor_for_the_scheduler(session: Session) -> None:
    """DEC-010: the scheduler records as `system-eod` with the internal SYSTEM role."""
    record = AuditService(session).record(
        action=AuditAction.RUN_END_OF_DAY,
        actor_id="system-eod",
        actor_role=ActorRole.SYSTEM,
        entity_type=AuditEntityType.END_OF_DAY,
        entity_id="2026-03-03",
        detail={"as_of": "2026-03-03", "renewed": 2, "lapsed": 0},
    )
    assert record.actor_role == ActorRole.SYSTEM.value
    assert record.entity_id == "2026-03-03"


def test_uses_the_bound_correlation_id(session: Session) -> None:
    """The row carries the request's correlation id (NFR-06)."""
    token = set_correlation_id("corr-audit-1")
    try:
        record = AuditService(session).record(
            action=AuditAction.UW_APPROVE,
            actor_id="uw-001",
            actor_role=ActorRole.UNDERWRITER,
            entity_type=AuditEntityType.APPLICATION,
            entity_id="app-1",
        )
    finally:
        reset_correlation_id(token)
    assert record.correlation_id == "corr-audit-1"


def test_detail_defaults_to_none(session: Session) -> None:
    """An action with nothing to say stores a null detail rather than an empty object."""
    record = AuditService(session).record(
        action=AuditAction.UW_DECLINE,
        actor_id="uw-001",
        actor_role=ActorRole.UNDERWRITER,
        entity_type=AuditEntityType.APPLICATION,
        entity_id="app-2",
    )
    assert record.detail is None


@pytest.mark.parametrize(
    "key", ["aadhaar", "pan", "health_declaration", "kyc", "full_name", "date_of_birth", "address"]
)
def test_detail_rejects_pii_keys(session: Session, key: str) -> None:
    """NFR-03: audit detail never carries PII — a PII key is refused, not silently stored."""
    with pytest.raises(ValueError, match="PII"):
        AuditService(session).record(
            action=AuditAction.UW_APPROVE,
            actor_id="uw-001",
            actor_role=ActorRole.UNDERWRITER,
            entity_type=AuditEntityType.APPLICATION,
            entity_id="app-3",
            detail={key: "999900000001"},
        )


@pytest.mark.parametrize(
    "detail",
    [
        {"outer": {"aadhaar": "999900000001"}},
        {"outer": [{"pan": "AAAAA0001A"}]},
        {"a": {"b": {"health_declaration": "asthma"}}},
    ],
)
def test_detail_rejects_nested_pii_keys(session: Session, detail: dict[str, Any]) -> None:
    """NFR-03: a PII key nested inside a dict or list is refused, not stored."""
    with pytest.raises(ValueError, match="PII"):
        AuditService(session).record(
            action=AuditAction.UW_APPROVE,
            actor_id="uw-001",
            actor_role=ActorRole.UNDERWRITER,
            entity_type=AuditEntityType.APPLICATION,
            entity_id="app-4",
            detail=detail,
        )


def test_detail_masks_pii_shapes_inside_free_text(session: Session) -> None:
    """NFR-03 / APP-W01: Aadhaar- and PAN-shaped substrings in prose are masked on the way in."""
    record = AuditService(session).record(
        action=AuditAction.UW_OVERRIDE_DECLINE,
        actor_id="admin-001",
        actor_role=ActorRole.ADMIN,
        entity_type=AuditEntityType.APPLICATION,
        entity_id="app-5",
        detail={"comment": "checked 9999 0000 0001 and AAAAA0001A by hand"},
    )
    assert record.detail is not None
    comment = record.detail["comment"]
    assert "999900000001" not in comment
    assert "9999 0000 0001" not in comment
    assert "AAAAA0001A" not in comment
    assert "XXXX-XXXX-0001" in comment
    assert "XXXXX0001X" in comment


def test_detail_masks_pii_shapes_at_any_depth(session: Session) -> None:
    """NFR-03: masking recurses through nested dicts and lists of strings."""
    record = AuditService(session).record(
        action=AuditAction.UW_APPROVE,
        actor_id="uw-001",
        actor_role=ActorRole.UNDERWRITER,
        entity_type=AuditEntityType.APPLICATION,
        entity_id="app-6",
        detail={
            "notes": ["see 999900000001", {"inner": "pan AAAAA0001A"}],
            "nested": {"comment": "999900000001"},
        },
    )
    assert record.detail is not None
    dumped = json.dumps(record.detail)
    assert "999900000001" not in dumped
    assert "AAAAA0001A" not in dumped
    assert record.detail["nested"]["comment"] == "XXXX-XXXX-0001"


def test_detail_leaves_ordinary_values_untouched(session: Session) -> None:
    """Masking is pattern-based: non-PII prose, numbers and booleans survive unchanged."""
    record = AuditService(session).record(
        action=AuditAction.RULE_VERSION_PUBLISHED,
        actor_id="admin-001",
        actor_role=ActorRole.ADMIN,
        entity_type=AuditEntityType.RULE_SET_VERSION,
        entity_id="MOTOR/v2",
        detail={"product": "MOTOR", "version": 2, "published": True, "note": "routine publish"},
    )
    assert record.detail == {
        "product": "MOTOR",
        "version": 2,
        "published": True,
        "note": "routine publish",
    }


def test_service_does_not_commit(session: Session) -> None:
    """Services own the transaction boundary; `record` only stages the row."""
    AuditService(session).record(
        action=AuditAction.POLICY_ISSUED,
        actor_id="admin-001",
        actor_role=ActorRole.ADMIN,
        entity_type=AuditEntityType.POLICY,
        entity_id="MO-2026-000123",
    )
    session.rollback()
    assert AuditService(session).list_for_entity(AuditEntityType.POLICY, "MO-2026-000123") == []
