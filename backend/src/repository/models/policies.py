"""The ``policies`` current projection (`specs/design/data-models.md` 5.6).

Money columns are ``Numeric(12, 2)`` mapped to :class:`~decimal.Decimal` — never ``Float``
(NFR-01). The row is a projection: ``status`` and endorsable attributes move forward while every
change appends a ``policy_state_transitions`` row in the same transaction (NFR-02).
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.repository.database import Base
from src.repository.models._common import _in_clause, _new_uuid, _now
from src.types.enums import PolicyStatus, ProductCode

POLICIES_TABLE: Final = "policies"

#: ``<TL|MO|HH>-<YYYY>-<6-digit sequence>`` (docs/conventions.md -> "API / auth stub").
POLICY_NUMBER_GLOB: Final = "[TMH][LOH]-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]"


class Policy(Base):
    """One policy term — the current projection of its lifecycle (AC-05, AC-10, AC-15)."""

    __tablename__ = POLICIES_TABLE
    __table_args__ = (
        UniqueConstraint("policy_number", name="uq_policies_policy_number"),
        UniqueConstraint("previous_policy_number", name="uq_policies_previous_policy_number"),
        CheckConstraint(_in_clause("product", ProductCode), name="ck_policies_product"),
        CheckConstraint(_in_clause("status", PolicyStatus), name="ck_policies_status"),
        CheckConstraint(f"policy_number GLOB '{POLICY_NUMBER_GLOB}'", name="ck_policies_number"),
        CheckConstraint("rule_version >= 1", name="ck_policies_rule_version"),
        CheckConstraint("sum_insured > 0", name="ck_policies_sum_insured"),
        CheckConstraint("premium > 0", name="ck_policies_premium"),
        CheckConstraint("currency = 'INR'", name="ck_policies_currency"),
        CheckConstraint("expiry_date > effective_date", name="ck_policies_term"),
        Index("ix_policies_customer_id", "customer_id"),
        Index("ix_policies_status_expiry_date", "status", "expiry_date"),
        Index("ix_policies_product_status", "product", "status"),
        Index(
            "uq_policies_new_business_application",
            "application_id",
            unique=True,
            sqlite_where=text("previous_policy_number IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    policy_number: Mapped[str] = mapped_column(String(14), nullable=False)
    product: Mapped[str] = mapped_column(String(16), nullable=False)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=False
    )
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sum_insured: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    premium: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    premium_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    nominees: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    previous_policy_number: Mapped[str | None] = mapped_column(
        String(14), ForeignKey("policies.policy_number"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        """Debug representation without the insured address or nominees (NFR-03)."""
        return f"Policy(policy_number={self.policy_number!r}, status={self.status!r})"
