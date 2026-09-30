"""Append-only repository for `audit_records` (NFR-02, NFR-04).

Exposes ``add(...)`` and read methods only — no update, no delete, no merge. The session is
supplied by the calling service, which owns the transaction: this repository never commits.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.repository.models import AuditAction, AuditEntityType, AuditRecord
from src.types.enums import ActorRole


class AuditRecordRepository:
    """Reads and appends audit rows; it has no mutating operation by design."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        action: AuditAction,
        actor_id: str,
        actor_role: ActorRole,
        entity_type: AuditEntityType,
        entity_id: str,
        detail: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> AuditRecord:
        """Append one audit row and flush it so its defaults are populated."""
        record = AuditRecord(
            action=action.value,
            actor_id=actor_id,
            actor_role=actor_role.value,
            entity_type=entity_type.value,
            entity_id=entity_id,
            detail=detail,
            correlation_id=correlation_id,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, record_id: str) -> AuditRecord | None:
        """Return the audit row with ``record_id``, or ``None`` when it does not exist."""
        return self._session.get(AuditRecord, record_id)

    def list_for_entity(self, entity_type: AuditEntityType, entity_id: str) -> list[AuditRecord]:
        """Return every audit row for one entity, oldest first (insertion order)."""
        statement = (
            select(AuditRecord)
            .where(
                AuditRecord.entity_type == entity_type.value,
                AuditRecord.entity_id == entity_id,
            )
            # `created_at` can tie at clock resolution, so insertion order is the tiebreaker.
            .order_by(AuditRecord.created_at.asc(), text("rowid"))
        )
        return list(self._session.execute(statement).scalars())
