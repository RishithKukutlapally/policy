"""Create ``policies`` and the four append-only lifecycle tables (E5-S2).

Mirrors `specs/design/data-models.md` sections 5.6 to 5.10. One revision creates every lifecycle
table so the endorsement, renewal and cancellation stories add no further schema (design decision).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRODUCTS = ("TERM_LIFE", "MOTOR", "HOUSEHOLD")
_POLICY_STATUSES = ("ACTIVE", "ENDORSED", "LAPSED", "CANCELLED", "RENEWED")
_ENDORSEMENT_TYPES = ("CHANGE_ADDRESS", "ADD_NOMINEE", "CHANGE_SUM_INSURED")
_REFUND_TYPES = ("FREE_LOOK", "PRO_RATA")
_NUMBER_GLOB = "[TMH][LOH]-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _policy_id() -> sa.Column[sa.String]:
    return sa.Column("policy_id", sa.String(length=36), nullable=False)


def _money(name: str) -> sa.Column[sa.Numeric]:
    return sa.Column(name, sa.Numeric(precision=12, scale=2), nullable=False)


def _actor_id() -> sa.Column[sa.String]:
    return sa.Column("actor_id", sa.String(length=64), nullable=False)


def _upgrade_policies() -> None:
    """Create the ``policies`` projection with its constraints and indexes."""
    op.create_table(
        "policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("policy_number", sa.String(length=14), nullable=False),
        sa.Column("product", sa.String(length=16), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("rating_inputs", sa.JSON(), nullable=False),
        _money("sum_insured"),
        _money("premium"),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("premium_due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("nominees", sa.JSON(), nullable=False),
        sa.Column("previous_policy_number", sa.String(length=14), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_policies"),
        sa.UniqueConstraint("policy_number", name="uq_policies_policy_number"),
        sa.UniqueConstraint("previous_policy_number", name="uq_policies_previous_policy_number"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_policies_application"
        ),
        sa.ForeignKeyConstraint(
            ["previous_policy_number"], ["policies.policy_number"], name="fk_policies_previous"
        ),
        sa.CheckConstraint(_in("product", _PRODUCTS), name="ck_policies_product"),
        sa.CheckConstraint(_in("status", _POLICY_STATUSES), name="ck_policies_status"),
        sa.CheckConstraint(f"policy_number GLOB '{_NUMBER_GLOB}'", name="ck_policies_number"),
        sa.CheckConstraint("rule_version >= 1", name="ck_policies_rule_version"),
        sa.CheckConstraint("sum_insured > 0", name="ck_policies_sum_insured"),
        sa.CheckConstraint("premium > 0", name="ck_policies_premium"),
        sa.CheckConstraint("currency = 'INR'", name="ck_policies_currency"),
        sa.CheckConstraint("expiry_date > effective_date", name="ck_policies_term"),
    )
    op.create_index("ix_policies_customer_id", "policies", ["customer_id"])
    op.create_index("ix_policies_status_expiry_date", "policies", ["status", "expiry_date"])
    op.create_index("ix_policies_product_status", "policies", ["product", "status"])
    op.create_index(
        "uq_policies_new_business_application",
        "policies",
        ["application_id"],
        unique=True,
        sqlite_where=sa.text("previous_policy_number IS NULL"),
    )


def _upgrade_transitions() -> None:
    """Create the append-only ``policy_state_transitions`` table."""
    op.create_table(
        "policy_state_transitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        _policy_id(),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        _actor_id(),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_policy_state_transitions"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], name="fk_transitions_policy"),
        sa.CheckConstraint(
            f"from_status IS NULL OR {_in('from_status', _POLICY_STATUSES)}",
            name="ck_transitions_from_status",
        ),
        sa.CheckConstraint(
            _in("to_status", _POLICY_STATUSES), name="ck_transitions_to_status"
        ),
        sa.CheckConstraint(
            "(from_status IS NULL AND to_status = 'ACTIVE') OR from_status IS NOT NULL",
            name="ck_transitions_creation",
        ),
    )
    op.create_index(
        "ix_transitions_policy_occurred_at",
        "policy_state_transitions",
        ["policy_id", "occurred_at"],
    )


def _upgrade_endorsements() -> None:
    """Create the append-only ``endorsements`` table."""
    op.create_table(
        "endorsements",
        sa.Column("id", sa.String(length=36), nullable=False),
        _policy_id(),
        sa.Column("type", sa.String(length=24), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        _money("premium_delta"),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("endorsement_date", sa.Date(), nullable=False),
        _actor_id(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_endorsements"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], name="fk_endorsements_policy"),
        sa.CheckConstraint(_in("type", _ENDORSEMENT_TYPES), name="ck_endorsements_type"),
        sa.CheckConstraint("rule_version >= 1", name="ck_endorsements_rule_version"),
    )
    op.create_index(
        "ix_endorsements_policy_created_at", "endorsements", ["policy_id", "created_at"]
    )


def _upgrade_payments() -> None:
    """Create the append-only ``premium_payments`` table."""
    op.create_table(
        "premium_payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        _policy_id(),
        sa.Column("due_date", sa.Date(), nullable=False),
        _money("amount"),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        _actor_id(),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_premium_payments"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], name="fk_premium_payments_policy"),
        sa.UniqueConstraint("policy_id", "due_date", name="uq_premium_payments_policy_due"),
        sa.CheckConstraint("amount > 0", name="ck_premium_payments_amount"),
        sa.CheckConstraint("rule_version >= 1", name="ck_premium_payments_rule_version"),
    )
    op.create_index("ix_premium_payments_due_date", "premium_payments", ["due_date"])


def _upgrade_refunds() -> None:
    """Create the append-only ``refunds`` table."""
    op.create_table(
        "refunds",
        sa.Column("id", sa.String(length=36), nullable=False),
        _policy_id(),
        sa.Column("refund_type", sa.String(length=16), nullable=False),
        _money("premium_paid"),
        sa.Column("term_days", sa.Integer(), nullable=False),
        sa.Column("days_elapsed", sa.Integer(), nullable=False),
        sa.Column("unused_days", sa.Integer(), nullable=False),
        _money("admin_fee"),
        _money("amount"),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("cancellation_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        _actor_id(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_refunds"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], name="fk_refunds_policy"),
        sa.UniqueConstraint("policy_id", name="uq_refunds_policy_id"),
        sa.CheckConstraint(_in("refund_type", _REFUND_TYPES), name="ck_refunds_type"),
        sa.CheckConstraint("premium_paid > 0", name="ck_refunds_premium_paid"),
        sa.CheckConstraint("term_days > 0", name="ck_refunds_term_days"),
        sa.CheckConstraint("days_elapsed >= 0", name="ck_refunds_days_elapsed"),
        sa.CheckConstraint("unused_days = term_days - days_elapsed", name="ck_refunds_unused_days"),
        sa.CheckConstraint("admin_fee >= 0", name="ck_refunds_admin_fee"),
        sa.CheckConstraint("amount >= 0 AND amount <= premium_paid", name="ck_refunds_amount"),
        sa.CheckConstraint("rule_version >= 1", name="ck_refunds_rule_version"),
    )


def upgrade() -> None:
    """Create the policy projection and every append-only lifecycle table."""
    _upgrade_policies()
    _upgrade_transitions()
    _upgrade_endorsements()
    _upgrade_payments()
    _upgrade_refunds()


def downgrade() -> None:
    """Append-only schema history: downgrade is intentionally a no-op (NFR-05)."""
