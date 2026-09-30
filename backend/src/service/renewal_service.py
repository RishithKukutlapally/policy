"""Renewal quote and renewal into a new linked policy term (AC-07, NFR-01, NFR-02, NFR-04).

The renewal premium is quoted on the product's *active* rule version with ages and
``vehicle_age_years`` advanced by one completed term. :meth:`RenewalService.renew` (customer) and
:meth:`RenewalService.apply_renewal` (also used by the end-of-day job) create the successor policy
term (new number, ``previous_policy_number`` set, ``ACTIVE``, its own ``NULL -> ACTIVE``
transition) and move the old policy to ``RENEWED`` with its transition row, all uncommitted until
the caller (or :meth:`renew`) commits, so either every row lands or none does.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Final

from sqlalchemy.orm import Session

from src.config.rule_loader import build_rule_set
from src.config.settings import get_settings
from src.domain.policy_state_machine import assert_transition, is_terminal
from src.domain.renewal_rules import RenewalSchedule, renewal_premium, renewal_schedule
from src.lib.clock import today
from src.repository.models import Policy, PremiumPayment
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.service.ownership import owned_policy
from src.service.policy_service import NUMBER_PREFIX, PolicySummaryView, summary_view
from src.service.quote_service import ActingActor, field_errors
from src.types.enums import PolicyStatus, ProductCode
from src.types.errors import (
    InvalidPolicyStateException,
    NoPublishedVersionError,
    OutsideRenewalWindowError,
    ValidationError,
)
from src.types.rules import RuleSet

RENEWED_REASON: Final = "RENEWED"
RENEWAL_REASON: Final = "RENEWAL"
_AGE_FIELDS: Final[Mapping[ProductCode, tuple[str, ...]]] = {
    ProductCode.TERM_LIFE: ("age",),
    ProductCode.MOTOR: ("owner_age", "vehicle_age_years"),
    ProductCode.HOUSEHOLD: ("proposer_age",),
}


@dataclass(frozen=True, slots=True)
class RenewalQuoteView:
    """Read model of ``GET /api/policies/{number}/renewal`` (contract 2.20)."""

    policy_number: str
    renewable: bool
    renewal_premium: Decimal | None
    rule_version: int
    currency: str
    due_date: date
    grace_end_date: date
    renewal_window_opens: date
    paid: bool


@dataclass(frozen=True, slots=True)
class RenewalContext:
    """Everything the renewal of one policy depends on, computed once."""

    rule_version: int
    schedule: RenewalSchedule
    window_opens: date
    renewable: bool
    premium: Decimal | None
    inputs: Mapping[str, Any]
    rule_set: RuleSet


def assert_live(policy: Policy, target: PolicyStatus) -> PolicyStatus:
    """The policy's status, or 409 ``INVALID_POLICY_STATE`` when it is terminal."""
    current = PolicyStatus(policy.status)
    if is_terminal(current):
        assert_transition(current, target)
    return current


def advance_inputs(policy: Policy, product: ProductCode, terms: int) -> dict[str, Any]:
    """Rating inputs one renewal on: ages advance by ``terms``, cover follows the policy."""
    inputs = dict(policy.rating_inputs)
    for name in _AGE_FIELDS[product]:
        inputs[name] = int(inputs[name]) + terms
    inputs["sum_insured"] = str(policy.sum_insured)
    return inputs


class RenewalService:
    """Quotes renewals and creates the successor term of a paid policy."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._policies = PolicyRepository(session)
        self._lifecycle = PolicyLifecycleRepository(session)
        self._versions = RuleSetVersionRepository(session)

    def build_context(self, policy: Policy) -> RenewalContext:
        """Quote the renewal of ``policy`` on the active version of its product."""
        product = ProductCode(policy.product)
        row = self._versions.active_for_product(product)
        if row is None:
            raise NoPublishedVersionError(f"Product {product.value} has no PUBLISHED rule version")
        rule_set = build_rule_set(row.content, label=f"{product.value} v{row.version}")
        schedule = renewal_schedule(rule_set, policy.expiry_date)
        inputs = advance_inputs(policy, product, max(1, rule_set.renewal.term_months // 12))
        premium = self._premium(rule_set, inputs)
        window_opens = policy.expiry_date - timedelta(days=get_settings().renewal_window_days)
        return RenewalContext(
            row.version, schedule, window_opens, premium is not None, premium, inputs, rule_set
        )

    @staticmethod
    def _premium(rule_set: RuleSet, inputs: Mapping[str, Any]) -> Decimal | None:
        """The refreshed premium, or ``None`` when the advanced inputs are not eligible."""
        if field_errors(rule_set, inputs):
            return None
        try:
            return renewal_premium(rule_set, inputs)
        except ValidationError:
            return None

    def payment_for(self, policy: Policy, due_date: date) -> PremiumPayment | None:
        """The premium payment recorded for ``due_date``, if any."""
        for payment in self._lifecycle.payments_of(policy.id):
            if payment.due_date == due_date:
                return payment
        return None

    def assert_window_open(self, policy: Policy, context: RenewalContext, on: date) -> None:
        """409 ``OUTSIDE_RENEWAL_WINDOW`` before the window opens or after the grace end."""
        if on < context.window_opens or on > context.schedule.grace_end:
            raise OutsideRenewalWindowError(
                "Renewal is outside the renewal window",
                {
                    "window_opens": context.window_opens.isoformat(),
                    "grace_end": context.schedule.grace_end.isoformat(),
                },
            )

    def renewal_quote(self, policy_number: str, actor: ActingActor) -> RenewalQuoteView:
        """Contract 2.20: the refreshed premium and dates; 409 before the window opens."""
        policy = owned_policy(self._policies, policy_number, actor)
        assert_live(policy, PolicyStatus.RENEWED)
        context = self.build_context(policy)
        if today() < context.window_opens:
            raise OutsideRenewalWindowError(
                "Renewal window has not opened", {"window_opens": context.window_opens.isoformat()}
            )
        paid = self.payment_for(policy, context.schedule.due_date) is not None
        return RenewalQuoteView(
            policy_number=policy.policy_number,
            renewable=context.renewable,
            renewal_premium=context.premium,
            rule_version=context.rule_version,
            currency=policy.currency,
            due_date=context.schedule.due_date,
            grace_end_date=context.schedule.grace_end,
            renewal_window_opens=context.window_opens,
            paid=paid,
        )

    def renew(self, policy_number: str, actor: ActingActor) -> PolicySummaryView:
        """Early / on-time renewal by the owner on the business date; commits once (AC-07)."""
        try:
            policy = owned_policy(self._policies, policy_number, actor)
            assert_live(policy, PolicyStatus.RENEWED)
            self.assert_window_open(policy, self.build_context(policy), today())
            view = self.apply_renewal(policy_number, today(), actor)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return view

    def apply_renewal(
        self, policy_number: str, as_of: date, actor: ActingActor
    ) -> PolicySummaryView:
        """Create the successor term and retire the old one; the caller commits."""
        policy = owned_policy(self._policies, policy_number, actor)
        current = assert_live(policy, PolicyStatus.RENEWED)
        if self._policies.successor_of(policy.policy_number) is not None:
            raise InvalidPolicyStateException(
                "Policy already has a renewal successor",
                {"current": current.value, "target": PolicyStatus.RENEWED.value},
            )
        context = self.build_context(policy)
        if not context.renewable:
            raise ValidationError(
                "Policy is not renewable", [{"field": "policy_number", "code": "NOT_RENEWABLE"}]
            )
        payment = self.payment_for(policy, context.schedule.due_date)
        if payment is None:
            raise ValidationError(
                "Renewal premium is unpaid",
                [{"field": "payment", "code": "RENEWAL_PREMIUM_UNPAID"}],
            )
        successor = self._insert_successor(policy, context, payment)
        assert_transition(current, PolicyStatus.RENEWED)
        self._policies.update_projection(policy, status=PolicyStatus.RENEWED)
        self._lifecycle.add_transition(
            policy_id=policy.id,
            from_status=current,
            to_status=PolicyStatus.RENEWED,
            reason=RENEWED_REASON,
            actor_id=actor.actor_id,
        )
        self._lifecycle.add_transition(
            policy_id=successor.id,
            from_status=None,
            to_status=PolicyStatus.ACTIVE,
            reason=RENEWAL_REASON,
            actor_id=actor.actor_id,
        )
        return summary_view(successor)

    def _insert_successor(
        self, policy: Policy, context: RenewalContext, payment: PremiumPayment
    ) -> Policy:
        """Insert the next term with the next free number of its product and year."""
        prefix = NUMBER_PREFIX[ProductCode(policy.product)]
        effective = context.schedule.effective_date
        sequence = self._policies.next_sequence(prefix, effective.year)
        return self._policies.add(
            policy_number=f"{prefix}-{effective.year:04d}-{sequence:06d}",
            product=policy.product,
            application_id=policy.application_id,
            customer_id=policy.customer_id,
            rule_version=payment.rule_version,
            rating_inputs=context.inputs,
            sum_insured=policy.sum_insured,
            premium=payment.amount,
            effective_date=effective,
            expiry_date=context.schedule.expiry_date,
            premium_due_date=effective,
            status=PolicyStatus.ACTIVE,
            address=policy.address,
            nominees=policy.nominees,
            previous_policy_number=policy.policy_number,
        )
