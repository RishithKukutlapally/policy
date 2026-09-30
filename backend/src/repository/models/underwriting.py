"""Applications and the append-only underwriting decision / override tables (NFR-02)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.repository.database import Base
from src.repository.models._common import _in_clause, _new_uuid, _now
from src.types.enums import ApplicationStatus, Decision, ProductCode


class Application(Base):
    """One application after synchronous underwriting (`data-models.md` 5.3).

    A status projection: ``status`` / ``status_history`` move with each decision while the
    decisions stay append-only. Only masked Aadhaar and PAN are stored (NFR-03).
    """

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(_in_clause("product", ProductCode), name="ck_applications_product"),
        CheckConstraint(_in_clause("status", ApplicationStatus), name="ck_applications_status"),
        CheckConstraint("kyc_status = 'VERIFIED'", name="ck_applications_kyc_status"),
        CheckConstraint("rule_version >= 1", name="ck_applications_rule_version"),
        Index("ix_applications_status_created_at", "status", "created_at"),
        Index("ix_applications_customer_id", "customer_id"),
        Index("ix_applications_quote_id", "quote_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    quote_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotes.id"), nullable=False)
    product: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    aadhaar_masked: Mapped[str] = mapped_column(String(14), nullable=False)
    pan_masked: Mapped[str] = mapped_column(String(10), nullable=False)
    kyc_status: Mapped[str] = mapped_column(String(16), nullable=False, default="VERIFIED")
    risk_inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    status_history: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        """Debug representation without any KYC field."""
        return f"Application(id={self.id!r}, product={self.product!r}, status={self.status!r})"


class UnderwritingDecision(Base):
    """One underwriting decision (SYSTEM or a human). Append-only (NFR-02)."""

    __tablename__ = "underwriting_decisions"
    __table_args__ = (
        CheckConstraint(_in_clause("decision", Decision), name="ck_uw_decisions_decision"),
        CheckConstraint(_in_clause("product", ProductCode), name="ck_uw_decisions_product"),
        CheckConstraint("rule_version >= 1", name="ck_uw_decisions_rule_version"),
        Index("ix_uw_decisions_application", "application_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    product: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decided_by: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class UnderwritingOverride(Base):
    """An admin override of a DECLINED application to AUTO_BIND. Append-only (NFR-02)."""

    __tablename__ = "underwriting_overrides"
    __table_args__ = (
        CheckConstraint("from_status = 'DECLINED'", name="ck_uw_overrides_from"),
        CheckConstraint("to_status = 'AUTO_BIND'", name="ck_uw_overrides_to"),
        CheckConstraint("length(comment) BETWEEN 10 AND 500", name="ck_uw_overrides_comment"),
        Index("ix_uw_overrides_application", "application_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=False
    )
    original_decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("underwriting_decisions.id"), nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(16), nullable=False, default="DECLINED")
    to_status: Mapped[str] = mapped_column(String(16), nullable=False, default="AUTO_BIND")
    reason_code: Mapped[str] = mapped_column(String(9), nullable=False)
    comment: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
