"""The ``quotes`` table (`specs/design/data-models.md` 5.2).

Money columns are ``Numeric(12, 2)`` mapped to :class:`~decimal.Decimal` — never ``Float``
(NFR-01).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.repository.database import Base
from src.repository.models._common import _in_clause, _new_uuid, _now
from src.types.enums import ProductCode

QUOTES_TABLE: Final = "quotes"


class Quote(Base):
    """One priced quote (`specs/design/data-models.md` 5.2). Insert-only in practice.

    Records the ``rule_version`` it was priced on so it can be re-priced identically later
    (AC-13). Carries no PII: ``inputs`` holds rating inputs only.
    """

    __tablename__ = QUOTES_TABLE
    __table_args__ = (
        CheckConstraint(_in_clause("product", ProductCode), name="ck_quotes_product"),
        CheckConstraint("rule_version >= 1", name="ck_quotes_rule_version"),
        CheckConstraint("sum_insured > 0", name="ck_quotes_sum_insured"),
        CheckConstraint("premium > 0", name="ck_quotes_premium"),
        CheckConstraint("currency = 'INR'", name="ck_quotes_currency"),
        Index("ix_quotes_actor_id", "actor_id"),
        Index("ix_quotes_product_rule_version", "product", "rule_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    product: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sum_insured: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    premium: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        """Debug representation without the inputs."""
        return f"Quote(id={self.id!r}, product={self.product!r}, rule_version={self.rule_version})"
