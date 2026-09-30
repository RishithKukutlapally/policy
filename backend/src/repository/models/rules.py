"""The append-only ``rule_set_versions`` table (DEC-013)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Final

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.repository.database import Base
from src.repository.models._common import _in_clause, _new_uuid, _now
from src.types.enums import ProductCode, RuleSetStatus

RULE_SET_VERSIONS_TABLE: Final = "rule_set_versions"

_RULE_SET_STATUSES: Final = tuple(member.value for member in RuleSetStatus)


class RuleSetVersion(Base):
    """One state change of a ``(product, version)`` rule set (DEC-013). Append-only.

    A DRAFT replacement appends ``revision + 1``; publishing appends the final row. The current
    state of a version is its row with the highest ``revision``. ``content`` is the full rule-file
    body with money and rates kept as **strings** so nothing is ever read back as a ``float``
    (NFR-01); ``content_sha256`` is the SHA-256 of the imported file bytes (`PUBLISHED.lock`).
    """

    __tablename__ = RULE_SET_VERSIONS_TABLE
    __table_args__ = (
        UniqueConstraint(
            "product", "version", "revision", name="uq_rule_set_versions_product_version_revision"
        ),
        CheckConstraint(_in_clause("product", ProductCode), name="ck_rule_set_versions_product"),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in _RULE_SET_STATUSES)})",
            name="ck_rule_set_versions_status",
        ),
        CheckConstraint("version >= 1", name="ck_rule_set_versions_version"),
        CheckConstraint("revision >= 1", name="ck_rule_set_versions_revision"),
        CheckConstraint("length(content_sha256) = 64", name="ck_rule_set_versions_sha256_length"),
        Index(
            "uq_rule_set_versions_published",
            "product",
            "version",
            unique=True,
            sqlite_where=text("status = 'PUBLISHED'"),
            postgresql_where=text("status = 'PUBLISHED'"),
        ),
        Index("ix_rule_set_versions_product_version", "product", "version", "revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    product: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        """Debug representation without the rule body."""
        return (
            f"RuleSetVersion(product={self.product!r}, version={self.version}, "
            f"revision={self.revision}, status={self.status!r})"
        )
