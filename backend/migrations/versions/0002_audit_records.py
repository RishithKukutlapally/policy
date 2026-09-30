"""Create the append-only ``audit_records`` table (E1-S3, NFR-02, NFR-04).

Columns and indexes mirror `specs/design/data-models.md` section 5.11. Append-only: no later
revision may drop or alter this table — fix forward with a new revision (NFR-05).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTOR_ROLES = ("CUSTOMER", "UNDERWRITER", "ADMIN", "SYSTEM")
_ACTIONS = (
    "RULE_VERSION_DRAFT_CREATED",
    "RULE_VERSION_DRAFT_REPLACED",
    "RULE_VERSION_PUBLISHED",
    "UW_APPROVE",
    "UW_DECLINE",
    "UW_OVERRIDE_DECLINE",
    "POLICY_ISSUED",
    "ENDORSEMENT_CREATED",
    "POLICY_CANCELLED",
    "RUN_END_OF_DAY",
)
_ENTITY_TYPES = ("RULE_SET_VERSION", "APPLICATION", "POLICY", "END_OF_DAY")


def _in_clause(column: str, values: Sequence[str]) -> str:
    """Render ``column IN ('A', 'B')`` for a CHECK constraint."""
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    """Create ``audit_records`` with its CHECK constraints and read indexes."""
    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_records"),
        sa.CheckConstraint(_in_clause("actor_role", _ACTOR_ROLES), name="ck_audit_records_actor_role"),
        sa.CheckConstraint(_in_clause("action", _ACTIONS), name="ck_audit_records_action"),
        sa.CheckConstraint(
            _in_clause("entity_type", _ENTITY_TYPES), name="ck_audit_records_entity_type"
        ),
    )
    op.create_index(
        "ix_audit_records_entity", "audit_records", ["entity_type", "entity_id", "created_at"]
    )
    op.create_index("ix_audit_records_action", "audit_records", ["action"])


def downgrade() -> None:
    """Append-only table: downgrade is intentionally a no-op (NFR-02/NFR-05)."""
