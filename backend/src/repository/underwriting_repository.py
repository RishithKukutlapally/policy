"""Append-only repositories for ``underwriting_decisions`` and ``underwriting_overrides``.

Public surface: ``add`` plus reads. No update and no delete (NFR-02). The calling service owns
the transaction; these repositories never commit.
"""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.repository.models import UnderwritingDecision, UnderwritingOverride
from src.types.enums import Decision


class UnderwritingDecisionRepository:
    """Appends decisions; a case's current decision is its latest row."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        application_id: str,
        decision: Decision,
        reason_codes: list[str],
        product: str,
        rule_version: int,
        decided_by: str,
        comment: str | None,
    ) -> UnderwritingDecision:
        """Insert one decision and flush it."""
        row = UnderwritingDecision(
            application_id=application_id,
            decision=decision.value,
            reason_codes=sorted(reason_codes),
            product=product,
            rule_version=rule_version,
            decided_by=decided_by,
            comment=comment,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_for_application(self, application_id: str) -> list[UnderwritingDecision]:
        """Every decision of one application, oldest first."""
        statement = (
            select(UnderwritingDecision)
            .where(UnderwritingDecision.application_id == application_id)
            .order_by(UnderwritingDecision.created_at.asc(), text("rowid"))
        )
        return list(self._session.execute(statement).scalars())

    def latest_for_application(self, application_id: str) -> UnderwritingDecision | None:
        """The most recent decision of one application, or ``None``."""
        rows = self.list_for_application(application_id)
        return rows[-1] if rows else None


class UnderwritingOverrideRepository:
    """Appends admin overrides of DECLINED applications."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        application_id: str,
        original_decision_id: str,
        reason_code: str,
        comment: str,
        actor_id: str,
    ) -> UnderwritingOverride:
        """Insert one override (DECLINED -> AUTO_BIND) and flush it."""
        row = UnderwritingOverride(
            application_id=application_id,
            original_decision_id=original_decision_id,
            reason_code=reason_code,
            comment=comment,
            actor_id=actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_for_application(self, application_id: str) -> list[UnderwritingOverride]:
        """Every override of one application, oldest first."""
        statement = (
            select(UnderwritingOverride)
            .where(UnderwritingOverride.application_id == application_id)
            .order_by(UnderwritingOverride.created_at.asc(), text("rowid"))
        )
        return list(self._session.execute(statement).scalars())
