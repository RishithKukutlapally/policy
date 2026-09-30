"""The append-only ``audit_records`` table and its enums (NFR-04)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Final

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.repository.database import Base
from src.repository.models._common import _in_clause, _new_uuid, _now
from src.types.enums import ActorRole


class AuditAction(StrEnum):
    """`audit_records.action` values (`docs/conventions.md` -> "Audit actions").

    Kept next to the model because `src/types/enums.py` is owned by another story; the CHECK
    constraint below is generated from this enum so the two can never drift.
    """

    RULE_VERSION_DRAFT_CREATED = "RULE_VERSION_DRAFT_CREATED"
    RULE_VERSION_DRAFT_REPLACED = "RULE_VERSION_DRAFT_REPLACED"
    RULE_VERSION_PUBLISHED = "RULE_VERSION_PUBLISHED"
    UW_APPROVE = "UW_APPROVE"
    UW_DECLINE = "UW_DECLINE"
    UW_OVERRIDE_DECLINE = "UW_OVERRIDE_DECLINE"
    POLICY_ISSUED = "POLICY_ISSUED"
    ENDORSEMENT_CREATED = "ENDORSEMENT_CREATED"
    POLICY_CANCELLED = "POLICY_CANCELLED"
    RUN_END_OF_DAY = "RUN_END_OF_DAY"


class AuditEntityType(StrEnum):
    """Entity an audit record points at (`specs/design/data-models.md` §5.11)."""

    RULE_SET_VERSION = "RULE_SET_VERSION"
    APPLICATION = "APPLICATION"
    POLICY = "POLICY"
    END_OF_DAY = "END_OF_DAY"


AUDIT_RECORDS_TABLE: Final = "audit_records"


class AuditRecord(Base):
    """One UNDERWRITER/ADMIN/scheduler action (NFR-04). Append-only — never updated or deleted.

    ``detail`` is a small JSON object that never contains PII (NFR-03); the audit service
    refuses PII keys before the row is staged.
    """

    __tablename__ = AUDIT_RECORDS_TABLE
    __table_args__ = (
        CheckConstraint(_in_clause("actor_role", ActorRole), name="ck_audit_records_actor_role"),
        CheckConstraint(_in_clause("action", AuditAction), name="ck_audit_records_action"),
        CheckConstraint(
            _in_clause("entity_type", AuditEntityType), name="ck_audit_records_entity_type"
        ),
        Index("ix_audit_records_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_records_action", "action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        """Debug representation without any detail payload."""
        return (
            f"AuditRecord(id={self.id!r}, action={self.action!r}, "
            f"entity={self.entity_type!r}/{self.entity_id!r})"
        )
