"""Admin portfolio dashboard read model (E9-S1, AC-20, NFR-01, NFR-04).

Aggregates the book as at an explicit ``as_of`` business date: in-force policies per product,
premium collected, refunds paid, the renewal pipeline and the lapse forecast for the next
``renewal_window_days``.

The service never prices anything — it reads the **stored** money of ``policies``,
``premium_payments`` and ``refunds`` (AC-01 keeps premiums in the rule files and the calculator).
Amounts are summed at full :class:`~decimal.Decimal` precision and quantized to ``0.01``
``ROUND_HALF_UP`` exactly once, on the way into the view. No PII is read or logged (NFR-03).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.config.rule_loader import load_rule_set
from src.config.settings import get_settings
from src.domain.money import to_money
from src.domain.renewal_rules import RenewalSchedule, renewal_schedule
from src.repository.models import Policy, PremiumPayment
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.service.quote_service import ActingActor
from src.types.enums import PolicyStatus, ProductCode
from src.types.rules import RuleSet

_ZERO = Decimal("0")

#: Statuses that count as in force for every dashboard figure (`specs/app_spec.md` §9).
IN_FORCE: frozenset[PolicyStatus] = frozenset({PolicyStatus.ACTIVE, PolicyStatus.ENDORSED})


@dataclass(frozen=True, slots=True)
class RenewalPipelineItemView:
    """One policy whose renewal falls due inside the look-ahead window."""

    policy_number: str
    product: str
    due_date: date
    renewal_premium: Decimal | None
    paid: bool


@dataclass(frozen=True, slots=True)
class LapseForecastItemView:
    """One unpaid in-grace policy and the date it is projected to lapse."""

    policy_number: str
    product: str
    due_date: date
    grace_end_date: date
    premium: Decimal


@dataclass(frozen=True, slots=True)
class LapseForecastView:
    """The projected lapses and the premium they put at risk."""

    count: int
    premium_at_risk: Decimal
    policies: tuple[LapseForecastItemView, ...]


@dataclass(frozen=True, slots=True)
class PortfolioView:
    """The whole dashboard payload for one ``as_of`` date."""

    as_of: date
    active_by_product: dict[str, int]
    sum_insured_by_product: dict[str, Decimal]
    premium_collected: Decimal
    refunds_paid: Decimal
    renewal_pipeline: tuple[RenewalPipelineItemView, ...]
    lapse_forecast: LapseForecastView


@dataclass(slots=True)
class _Totals:
    """Mutable accumulators used while walking the book."""

    counts: dict[str, int]
    sums: dict[str, Decimal]
    collected: Decimal = _ZERO
    refunded: Decimal = _ZERO

    @classmethod
    def empty(cls) -> _Totals:
        """Zeroed accumulators with every product code present (AC-20)."""
        return cls(
            counts={code.value: 0 for code in ProductCode},
            sums={code.value: _ZERO for code in ProductCode},
        )


def _paid_payment(
    payments: Sequence[PremiumPayment], due_date: date, as_of: date
) -> PremiumPayment | None:
    """The payment settling ``due_date`` on or before ``as_of``, when one exists."""
    for payment in payments:
        if payment.due_date == due_date and payment.paid_at.date() <= as_of:
            return payment
    return None


class RepositoryRuleContentSource:
    """Database-backed :class:`~src.config.rule_loader.RuleContentSource` (AC-11).

    Returns the body of the highest-``revision`` row of ``(product, version)``, so a version
    published through the admin UI — which has no file in `backend/policy_rules` — is loadable by
    the same call that loads the seeded ``v1`` files.
    """

    def __init__(self, versions: RuleSetVersionRepository) -> None:
        self._versions = versions

    def rule_content(self, product: ProductCode, version: int) -> Mapping[str, Any] | None:
        """Stored body of ``(product, version)``, or ``None`` when no row exists."""
        rows = [row for row in self._versions.list_for_product(product) if row.version == version]
        if not rows:
            return None
        return dict(max(rows, key=lambda row: row.revision).content)


class PortfolioService:
    """Builds the admin portfolio view from the canonical tables (read-only)."""

    def __init__(self, session: Session) -> None:
        self._policies = PolicyRepository(session)
        self._lifecycle = PolicyLifecycleRepository(session)
        self._rule_content = RepositoryRuleContentSource(RuleSetVersionRepository(session))
        self._window = get_settings().renewal_window_days
        self._rule_sets: dict[tuple[str, int], RuleSet] = {}

    def portfolio(self, as_of: date, actor: ActingActor) -> PortfolioView:
        """Aggregate the book as at ``as_of`` for ``actor`` (role checked at the API layer)."""
        del actor  # authorisation is the API layer's job (NFR-04); no PII is read here.
        horizon = as_of + timedelta(days=self._window)
        totals = _Totals.empty()
        pipeline: list[RenewalPipelineItemView] = []
        forecast: list[LapseForecastItemView] = []
        for policy in self._policies.list_all():
            payments = self._lifecycle.payments_of(policy.id)
            totals.collected += sum(
                (pay.amount for pay in payments if pay.paid_at.date() <= as_of), _ZERO
            )
            totals.refunded += sum(
                (
                    refund.amount
                    for refund in self._lifecycle.refunds_of(policy.id)
                    if refund.created_at.date() <= as_of
                ),
                _ZERO,
            )
            if PolicyStatus(policy.status) not in IN_FORCE:
                continue
            totals.counts[policy.product] += 1
            totals.sums[policy.product] += policy.sum_insured
            self._classify(policy, payments, as_of, horizon, pipeline, forecast)
        return self._view(as_of, totals, pipeline, forecast)

    def _classify(
        self,
        policy: Policy,
        payments: Sequence[PremiumPayment],
        as_of: date,
        horizon: date,
        pipeline: list[RenewalPipelineItemView],
        forecast: list[LapseForecastItemView],
    ) -> None:
        """Place one in-force policy in the renewal pipeline and/or the lapse forecast."""
        schedule = self._schedule(policy)
        settled = _paid_payment(payments, schedule.due_date, as_of)
        if as_of < schedule.due_date <= horizon:
            pipeline.append(
                RenewalPipelineItemView(
                    policy_number=policy.policy_number,
                    product=policy.product,
                    due_date=schedule.due_date,
                    renewal_premium=to_money(policy.premium if settled is None else settled.amount),
                    paid=settled is not None,
                )
            )
        in_grace = settled is None and schedule.due_date <= as_of <= schedule.grace_end
        if in_grace and schedule.grace_end <= horizon:
            forecast.append(
                LapseForecastItemView(
                    policy_number=policy.policy_number,
                    product=policy.product,
                    due_date=schedule.due_date,
                    grace_end_date=schedule.grace_end,
                    premium=to_money(policy.premium),
                )
            )

    def _schedule(self, policy: Policy) -> RenewalSchedule:
        """The next term's due date and grace end, from the policy's own rule version."""
        key = (policy.product, policy.rule_version)
        rule_set = self._rule_sets.get(key)
        if rule_set is None:
            rule_set = load_rule_set(
                ProductCode(policy.product), policy.rule_version, source=self._rule_content
            )
            self._rule_sets[key] = rule_set
        return renewal_schedule(rule_set, policy.expiry_date)

    @staticmethod
    def _view(
        as_of: date,
        totals: _Totals,
        pipeline: list[RenewalPipelineItemView],
        forecast: list[LapseForecastItemView],
    ) -> PortfolioView:
        """Assemble the immutable view, quantizing each accumulated amount once."""
        pipeline.sort(key=lambda item: (item.due_date, item.policy_number))
        forecast.sort(key=lambda item: (item.grace_end_date, item.policy_number))
        at_risk = sum((item.premium for item in forecast), _ZERO)
        return PortfolioView(
            as_of=as_of,
            active_by_product=dict(totals.counts),
            sum_insured_by_product={code: to_money(amount) for code, amount in totals.sums.items()},
            premium_collected=to_money(totals.collected),
            refunds_paid=to_money(totals.refunded),
            renewal_pipeline=tuple(pipeline),
            lapse_forecast=LapseForecastView(
                count=len(forecast),
                premium_at_risk=to_money(at_risk),
                policies=tuple(forecast),
            ),
        )
