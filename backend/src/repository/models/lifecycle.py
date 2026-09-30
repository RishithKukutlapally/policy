"""Append-only policy lifecycle tables (`specs/design/data-models.md` 5.7 to 5.10).

``policy_state_transitions``, ``endorsements``, ``premium_payments`` and ``refunds`` are written
once and never updated or deleted (NFR-02); their repositories expose ``add`` plus reads only.
Money columns are ``Numeric(12, 2)`` mapped to :class:`~decimal.Decimal` — never ``Float`` (NFR-01).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.repository.database import Base
from src.repository.models._common import _in_clause, _new_uuid, _now
from src.types.enums import EndorsementType, PolicyStatus, RefundType

POLICY_STATE_TRANSITIONS_TABLE: Final = "policy_state_transitions"
ENDORSEMENTS_TABLE: Final = "endorsements"
PREMIUM_PAYMENTS_TABLE: Final = "premium_payments"
REFUNDS_TABLE: Final = "refunds"

_POLICY_ID: Final = "policies.id"


class PolicyStateTransition(Base):
    """One recorded lifecycle step of a policy (AC-05, AC-10). Append-only."""

    __tablename__ = POLICY_STATE_TRANSITIONS_TABLE
    __table_args__ = (
        CheckConstraint(
            f"from_status IS NULL OR {_in_clause('from_status', PolicyStatus)}",
            name="ck_transitions_from_status",
        ),
        CheckConstraint(_in_clause("to_status", PolicyStatus), name="ck_transitions_to_status"),
        CheckConstraint(
            "(from_status IS NULL AND to_status = 'ACTIVE') OR from_status IS NOT NULL",
            name="ck_transitions_creation",
        ),
        Index("ix_transitions_policy_occurred_at", "policy_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey(_POLICY_ID), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class Endorsement(Base):
    """One mid-term policy change with its before/after values (AC-06). Append-only."""

    __tablename__ = ENDORSEMENTS_TABLE
    __table_args__ = (
        CheckConstraint(_in_clause("type", EndorsementType), name="ck_endorsements_type"),
        CheckConstraint("rule_version >= 1", name="ck_endorsements_rule_version"),
        Index("ix_endorsements_policy_created_at", "policy_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey(_POLICY_ID), nullable=False)
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    before: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    after: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    premium_delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    endorsement_date: Mapped[date] = mapped_column(Date, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class PremiumPayment(Base):
    """One premium payment for a term (AC-05 first term, AC-07 renewal). Append-only."""

    __tablename__ = PREMIUM_PAYMENTS_TABLE
    __table_args__ = (
        UniqueConstraint("policy_id", "due_date", name="uq_premium_payments_policy_due"),
        CheckConstraint("amount > 0", name="ck_premium_payments_amount"),
        CheckConstraint("rule_version >= 1", name="ck_premium_payments_rule_version"),
        Index("ix_premium_payments_due_date", "due_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey(_POLICY_ID), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class Refund(Base):
    """The single refund of a cancelled policy (AC-08). Append-only."""

    __tablename__ = REFUNDS_TABLE
    __table_args__ = (
        UniqueConstraint("policy_id", name="uq_refunds_policy_id"),
        CheckConstraint(_in_clause("refund_type", RefundType), name="ck_refunds_type"),
        CheckConstraint("premium_paid > 0", name="ck_refunds_premium_paid"),
        CheckConstraint("term_days > 0", name="ck_refunds_term_days"),
        CheckConstraint("days_elapsed >= 0", name="ck_refunds_days_elapsed"),
        CheckConstraint("unused_days = term_days - days_elapsed", name="ck_refunds_unused_days"),
        CheckConstraint("admin_fee >= 0", name="ck_refunds_admin_fee"),
        CheckConstraint("amount >= 0 AND amount <= premium_paid", name="ck_refunds_amount"),
        CheckConstraint("rule_version >= 1", name="ck_refunds_rule_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey(_POLICY_ID), nullable=False)
    refund_type: Mapped[str] = mapped_column(String(16), nullable=False)
    premium_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    days_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)
    unused_days: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    cancellation_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
