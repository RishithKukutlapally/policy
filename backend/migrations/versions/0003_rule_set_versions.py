"""Create the append-only ``rule_set_versions`` table (E2-S2, DEC-013, NFR-02/NFR-05).

Columns, constraints and indexes mirror `specs/design/data-models.md` section 5.1: a unique
constraint on (`product`, `version`, `revision`) and a **partial** unique index on
(`product`, `version`) where `status = 'PUBLISHED'`, so a version can be published exactly once
while DRAFT replacements append `revision + 1`.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRODUCTS = ("TERM_LIFE", "MOTOR", "HOUSEHOLD")
_STATUSES = ("DRAFT", "PUBLISHED")


def _in_clause(column: str, values: Sequence[str]) -> str:
    """Render ``column IN ('A', 'B')`` for a CHECK constraint."""
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    """Create ``rule_set_versions`` with its CHECK constraints and DEC-013 unique rules."""
    op.create_table(
        "rule_set_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_rule_set_versions"),
        sa.UniqueConstraint(
            "product", "version", "revision", name="uq_rule_set_versions_product_version_revision"
        ),
        sa.CheckConstraint(_in_clause("product", _PRODUCTS), name="ck_rule_set_versions_product"),
        sa.CheckConstraint(_in_clause("status", _STATUSES), name="ck_rule_set_versions_status"),
        sa.CheckConstraint("version >= 1", name="ck_rule_set_versions_version"),
        sa.CheckConstraint("revision >= 1", name="ck_rule_set_versions_revision"),
        sa.CheckConstraint(
            "length(content_sha256) = 64", name="ck_rule_set_versions_sha256_length"
        ),
    )
    op.create_index(
        "uq_rule_set_versions_published",
        "rule_set_versions",
        ["product", "version"],
        unique=True,
        sqlite_where=sa.text("status = 'PUBLISHED'"),
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )
    op.create_index(
        "ix_rule_set_versions_product_version",
        "rule_set_versions",
        ["product", "version", "revision"],
    )


def downgrade() -> None:
    """Append-only table: downgrade is intentionally a no-op (NFR-02/NFR-05)."""
