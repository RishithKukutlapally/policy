"""Baseline revision - establishes the migration chain; creates no tables.

Later stories append revisions on top of this one (migrations are append-only, NFR-05).

Revision ID: 0001
Revises:
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op baseline."""


def downgrade() -> None:
    """No-op baseline."""
