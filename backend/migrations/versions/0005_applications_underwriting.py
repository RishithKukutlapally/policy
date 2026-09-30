"""Create ``applications``, ``underwriting_decisions`` and ``underwriting_overrides`` (E4-S2..S4).

Mirrors `specs/design/data-models.md` sections 5.3 to 5.5. Only masked Aadhaar/PAN columns exist;
the decision and override tables are append-only by repository contract (NFR-02).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRODUCTS = ("TERM_LIFE", "MOTOR", "HOUSEHOLD")
_STATUSES = ("SUBMITTED", "UNDERWRITING", "AUTO_BIND", "MANUAL_REVIEW", "DECLINED", "ISSUED")
_DECISIONS = ("AUTO_BIND", "MANUAL_REVIEW", "DECLINE")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _created_at() -> sa.Column[sa.DateTime]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    """Create the three underwriting tables with constraints and indexes."""
    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("quote_id", sa.String(length=36), nullable=False),
        sa.Column("product", sa.String(length=16), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("aadhaar_masked", sa.String(length=14), nullable=False),
        sa.Column("pan_masked", sa.String(length=10), nullable=False),
        sa.Column("kyc_status", sa.String(length=16), nullable=False),
        sa.Column("risk_inputs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_history", sa.JSON(), nullable=False),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_applications"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], name="fk_applications_quote_id"),
        sa.CheckConstraint(_in("product", _PRODUCTS), name="ck_applications_product"),
        sa.CheckConstraint(_in("status", _STATUSES), name="ck_applications_status"),
        sa.CheckConstraint("kyc_status = 'VERIFIED'", name="ck_applications_kyc_status"),
        sa.CheckConstraint("rule_version >= 1", name="ck_applications_rule_version"),
    )
    op.create_index("ix_applications_status_created_at", "applications", ["status", "created_at"])
    op.create_index("ix_applications_customer_id", "applications", ["customer_id"])
    op.create_index("ix_applications_quote_id", "applications", ["quote_id"])
    op.create_table(
        "underwriting_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("product", sa.String(length=16), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("decided_by", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_underwriting_decisions"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_uw_decisions_application"
        ),
        sa.CheckConstraint(_in("decision", _DECISIONS), name="ck_uw_decisions_decision"),
        sa.CheckConstraint(_in("product", _PRODUCTS), name="ck_uw_decisions_product"),
        sa.CheckConstraint("rule_version >= 1", name="ck_uw_decisions_rule_version"),
    )
    op.create_index(
        "ix_uw_decisions_application", "underwriting_decisions", ["application_id", "created_at"]
    )
    op.create_table(
        "underwriting_overrides",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("original_decision_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=False),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=9), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_underwriting_overrides"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_uw_overrides_application"
        ),
        sa.ForeignKeyConstraint(
            ["original_decision_id"], ["underwriting_decisions.id"], name="fk_uw_overrides_decision"
        ),
        sa.CheckConstraint("from_status = 'DECLINED'", name="ck_uw_overrides_from"),
        sa.CheckConstraint("to_status = 'AUTO_BIND'", name="ck_uw_overrides_to"),
        sa.CheckConstraint("length(comment) BETWEEN 10 AND 500", name="ck_uw_overrides_comment"),
    )
    op.create_index("ix_uw_overrides_application", "underwriting_overrides", ["application_id"])


def downgrade() -> None:
    """Append-only schema history: downgrade is intentionally a no-op (NFR-05)."""
