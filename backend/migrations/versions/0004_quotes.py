"""Create the insert-only ``quotes`` table (E3-S2, AC-13).

Mirrors `specs/design/data-models.md` section 5.2. Money is ``Numeric(12, 2)``; ``rule_version``
records the version a quote was priced on so it can be re-priced identically.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRODUCTS = ("TERM_LIFE", "MOTOR", "HOUSEHOLD")


def upgrade() -> None:
    """Create ``quotes`` with its CHECK constraints and indexes."""
    products = ", ".join(repr(value) for value in _PRODUCTS)
    op.create_table(
        "quotes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product", sa.String(length=16), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("sum_insured", sa.Numeric(12, 2), nullable=False),
        sa.Column("premium", sa.Numeric(12, 2), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quotes"),
        sa.CheckConstraint(f"product IN ({products})", name="ck_quotes_product"),
        sa.CheckConstraint("rule_version >= 1", name="ck_quotes_rule_version"),
        sa.CheckConstraint("sum_insured > 0", name="ck_quotes_sum_insured"),
        sa.CheckConstraint("premium > 0", name="ck_quotes_premium"),
        sa.CheckConstraint("currency = 'INR'", name="ck_quotes_currency"),
    )
    op.create_index("ix_quotes_actor_id", "quotes", ["actor_id"])
    op.create_index("ix_quotes_product_rule_version", "quotes", ["product", "rule_version"])


def downgrade() -> None:
    """Append-only schema history: downgrade is intentionally a no-op (NFR-05)."""
