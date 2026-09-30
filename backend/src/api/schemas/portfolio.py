"""Response schemas for ``GET /api/admin/portfolio`` (contract 2.26, AC-20).

Money is serialised as a two-decimal string and dates as ISO-8601 (NFR-01, `docs/conventions.md`
-> "API / auth stub"). The payload carries no policyholder identity at all (NFR-03).
"""

from __future__ import annotations

from pydantic import BaseModel

from src.api.schemas.quotes import money
from src.service.portfolio_service import (
    LapseForecastItemView,
    LapseForecastView,
    PortfolioView,
    RenewalPipelineItemView,
)


class RenewalPipelineItemResponse(BaseModel):
    """One renewal falling due inside the look-ahead window."""

    policy_number: str
    product: str
    due_date: str
    renewal_premium: str | None
    paid: bool

    @classmethod
    def from_view(cls, view: RenewalPipelineItemView) -> RenewalPipelineItemResponse:
        """Build from a renewal pipeline item view."""
        return cls(
            policy_number=view.policy_number,
            product=view.product,
            due_date=view.due_date.isoformat(),
            renewal_premium=None if view.renewal_premium is None else money(view.renewal_premium),
            paid=view.paid,
        )


class LapseForecastItemResponse(BaseModel):
    """One unpaid in-grace policy and the date it is projected to lapse."""

    policy_number: str
    product: str
    due_date: str
    grace_end_date: str
    premium: str

    @classmethod
    def from_view(cls, view: LapseForecastItemView) -> LapseForecastItemResponse:
        """Build from a lapse forecast item view."""
        return cls(
            policy_number=view.policy_number,
            product=view.product,
            due_date=view.due_date.isoformat(),
            grace_end_date=view.grace_end_date.isoformat(),
            premium=money(view.premium),
        )


class LapseForecastResponse(BaseModel):
    """The projected lapses and the premium they put at risk."""

    count: int
    premium_at_risk: str
    policies: list[LapseForecastItemResponse]

    @classmethod
    def from_view(cls, view: LapseForecastView) -> LapseForecastResponse:
        """Build from the lapse forecast view."""
        return cls(
            count=view.count,
            premium_at_risk=money(view.premium_at_risk),
            policies=[LapseForecastItemResponse.from_view(item) for item in view.policies],
        )


class PortfolioResponse(BaseModel):
    """``GET /api/admin/portfolio`` body (`specs/app_spec.md` §9)."""

    as_of: str
    active_by_product: dict[str, int]
    sum_insured_by_product: dict[str, str]
    premium_collected: str
    refunds_paid: str
    renewal_pipeline: list[RenewalPipelineItemResponse]
    lapse_forecast: LapseForecastResponse

    @classmethod
    def from_view(cls, view: PortfolioView) -> PortfolioResponse:
        """Build the whole dashboard payload from the service view."""
        return cls(
            as_of=view.as_of.isoformat(),
            active_by_product=dict(view.active_by_product),
            sum_insured_by_product={
                code: money(amount) for code, amount in view.sum_insured_by_product.items()
            },
            premium_collected=money(view.premium_collected),
            refunds_paid=money(view.refunds_paid),
            renewal_pipeline=[
                RenewalPipelineItemResponse.from_view(item) for item in view.renewal_pipeline
            ],
            lapse_forecast=LapseForecastResponse.from_view(view.lapse_forecast),
        )
