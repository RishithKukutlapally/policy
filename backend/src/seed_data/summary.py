"""The one-line JSON summary the seed logs (E9-S3).

Counts are read back from the database, so the numbers describe what is actually there — on a
repeat run they are identical and ``inserted`` is ``False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.repository.models import (
    Application,
    Endorsement,
    Policy,
    PremiumPayment,
    Quote,
    Refund,
    RuleSetVersion,
    UnderwritingDecision,
)
from src.types.enums import RuleSetStatus


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    """What one seed run left behind, ready to be logged as a single JSON line."""

    inserted: bool
    counts: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        """The ``extra`` mapping of the seed's summary log record."""
        return {"event": "seed_portfolio_completed", "inserted": self.inserted, **self.counts}


def _total(session: Session, model: type) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def _grouped(session: Session, column: Any, model: type) -> dict[str, int]:
    rows = session.execute(select(column, func.count()).select_from(model).group_by(column)).all()
    return {str(key): int(count) for key, count in sorted(rows)}


def count_portfolio(session: Session) -> dict[str, Any]:
    """Counts of products, quotes, applications by decision, policies by status and money rows."""
    published = session.execute(
        select(func.count())
        .select_from(RuleSetVersion)
        .where(RuleSetVersion.status == RuleSetStatus.PUBLISHED.value)
    ).scalar_one()
    return {
        "products": int(published),
        "quotes": _total(session, Quote),
        "applications": _total(session, Application),
        "applications_by_decision": _grouped(
            session, UnderwritingDecision.decision, UnderwritingDecision
        ),
        "policies": _total(session, Policy),
        "policies_by_status": _grouped(session, Policy.status, Policy),
        "endorsements": _total(session, Endorsement),
        "payments": _total(session, PremiumPayment),
        "refunds": _total(session, Refund),
    }


def summarise(session: Session, *, inserted: bool) -> PortfolioSummary:
    """Read the current counts back into a :class:`PortfolioSummary`."""
    return PortfolioSummary(inserted=inserted, counts=count_portfolio(session))
