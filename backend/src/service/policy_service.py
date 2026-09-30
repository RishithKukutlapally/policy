"""Policy issuance and lifecycle transitions (AC-05, AC-10, NFR-01, NFR-02, NFR-04).

:meth:`PolicyService.issue` turns an ``AUTO_BIND`` application into an ``ACTIVE`` policy in one
transaction: it allocates the next ``<TL|MO|HH>-<YYYY>-<6-digit>`` number, inserts the policy,
appends the ``NULL -> ACTIVE`` transition and the first-term premium payment, audits the action for
staff actors and moves the application to ``ISSUED``. Nothing is committed until every write
succeeded (AC-06 rollback path). Services return view dataclasses, never ORM rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.policy_state_machine import assert_transition
from src.lib.clock import today
from src.repository.application_repository import ApplicationRepository
from src.repository.models import Application, AuditAction, AuditEntityType, Policy, Quote
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.repository.quote_repository import QuoteRepository
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.service.application_service import ApplicationReader
from src.service.audit_service import AuditService
from src.service.ownership import owned_policy
from src.service.quote_service import ActingActor
from src.types.enums import ActorRole, ApplicationStatus, PolicyStatus, ProductCode
from src.types.errors import (
    InvalidApplicationStateError,
    NotFoundError,
)

#: Policy-number prefix per product (`docs/conventions.md` -> Products and rule files).
NUMBER_PREFIX: Final[dict[ProductCode, str]] = {
    ProductCode.TERM_LIFE: "TL",
    ProductCode.MOTOR: "MO",
    ProductCode.HOUSEHOLD: "HH",
}
ISSUED_REASON: Final = "ISSUED"
#: Retries when two concurrent issuances pick the same sequence (UNIQUE constraint decides).
MAX_NUMBER_ATTEMPTS: Final = 5

_STAFF_ROLES: Final = frozenset({ActorRole.ADMIN})


@dataclass(frozen=True, slots=True)
class PolicySummaryView:
    """Read model of one policy term (contract `PolicySummary`)."""

    policy_number: str
    product: str
    status: str
    rule_version: int
    sum_insured: Decimal
    premium: Decimal
    currency: str
    effective_date: date
    expiry_date: date
    premium_due_date: date
    previous_policy_number: str | None

    @property
    def next_premium_due_date(self) -> date:
        """Renewal due date, derived as ``expiry_date + 1 day`` (AC-15)."""
        return self.expiry_date + _ONE_DAY


_ONE_DAY: Final = date(2000, 1, 2) - date(2000, 1, 1)


def summary_view(row: Policy) -> PolicySummaryView:
    """Copy a stored policy into its summary view."""
    return PolicySummaryView(
        policy_number=row.policy_number,
        product=row.product,
        status=row.status,
        rule_version=row.rule_version,
        sum_insured=row.sum_insured,
        premium=row.premium,
        currency=row.currency,
        effective_date=row.effective_date,
        expiry_date=row.expiry_date,
        premium_due_date=row.premium_due_date,
        previous_policy_number=row.previous_policy_number,
    )


def add_months(start: date, months: int) -> date:
    """``start`` shifted by whole ``months``, clamped to the last day of the target month."""
    total = start.month - 1 + months
    year, month = start.year + total // 12, total % 12 + 1
    last_day = (date(year + month // 12, month % 12 + 1, 1) - _ONE_DAY).day
    return date(year, month, min(start.day, last_day))


def term_end(effective_date: date, term_months: int) -> date:
    """Inclusive expiry date of a ``term_months`` term starting on ``effective_date``."""
    return add_months(effective_date, term_months) - _ONE_DAY


class PolicyService(ApplicationReader):
    """Issues policies and performs audited lifecycle transitions."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._policies = PolicyRepository(session)
        self._lifecycle = PolicyLifecycleRepository(session)
        self._quotes = QuoteRepository(session)
        self._application_rows = ApplicationRepository(session)
        self._audit = AuditService(session)
        self._version_rows = RuleSetVersionRepository(session)

    def issue(self, application_id: str, actor: ActingActor) -> PolicySummaryView:
        """Issue the policy of an ``AUTO_BIND`` application in one transaction (AC-05).

        The policy insert is the first write of the transaction, so a lost race on the number
        (``UNIQUE`` on ``policies.policy_number``) is retried by rolling the whole attempt back
        and re-allocating — the pysqlite driver cannot nest a SAVEPOINT here.
        """
        for _ in range(MAX_NUMBER_ATTEMPTS):
            try:
                return self._issue_once(application_id, actor)
            except IntegrityError:
                self._session.rollback()
        raise InvalidApplicationStateError(
            "Could not allocate a policy number", {"application_id": application_id}
        )

    def _issue_once(self, application_id: str, actor: ActingActor) -> PolicySummaryView:
        """One issuance attempt: every write plus the single commit (AC-05, NFR-02)."""
        application = self._application_rows.get(application_id)
        if application is None or (
            actor.role is ActorRole.CUSTOMER and application.customer_id != actor.actor_id
        ):
            raise NotFoundError("Application not found")
        if application.status != ApplicationStatus.AUTO_BIND.value:
            raise InvalidApplicationStateError(
                "Only an AUTO_BIND application can be issued",
                {"current": application.status, "required": ApplicationStatus.AUTO_BIND.value},
            )
        quote = self._quotes.get(application.quote_id)
        if quote is None:  # pragma: no cover - guarded by the applications FK
            raise NotFoundError("Quote not found")
        rule_set = self.rule_set_for(application.product, application.rule_version)
        effective = today()
        try:
            policy = self._insert_policy(
                application=application,
                quote=quote,
                effective=effective,
                expiry=term_end(effective, rule_set.renewal.term_months),
            )
            self._lifecycle.add_transition(
                policy_id=policy.id,
                from_status=None,
                to_status=PolicyStatus.ACTIVE,
                reason=ISSUED_REASON,
                actor_id=actor.actor_id,
            )
            self._lifecycle.add_payment(
                policy_id=policy.id,
                due_date=policy.effective_date,
                amount=policy.premium,
                rule_version=policy.rule_version,
                actor_id=actor.actor_id,
            )
            if actor.role in _STAFF_ROLES:
                self._audit.record(
                    action=AuditAction.POLICY_ISSUED,
                    actor_id=actor.actor_id,
                    actor_role=actor.role,
                    entity_type=AuditEntityType.POLICY,
                    entity_id=policy.policy_number,
                    detail={"product": policy.product, "rule_version": policy.rule_version},
                )
            self._application_rows.transition(application, ApplicationStatus.ISSUED)
            self._session.commit()
        except IntegrityError:
            raise
        except BaseException:
            self._session.rollback()
            raise
        return summary_view(policy)

    def transition(
        self, policy_number: str, target: PolicyStatus, *, reason: str, actor: ActingActor
    ) -> PolicySummaryView:
        """Move a policy to ``target`` and append the transition; 409 when disallowed (AC-10).

        The caller owns the transaction: this method flushes but never commits.
        """
        policy = owned_policy(self._policies, policy_number, actor)
        current = PolicyStatus(policy.status)
        assert_transition(current, target)
        self._policies.update_projection(policy, status=target)
        self._lifecycle.add_transition(
            policy_id=policy.id,
            from_status=current,
            to_status=target,
            reason=reason,
            actor_id=actor.actor_id,
        )
        return summary_view(policy)

    def _insert_policy(
        self, *, application: Application, quote: Quote, effective: date, expiry: date
    ) -> Policy:
        """Insert the policy with the next free number of its product and year."""
        product = ProductCode(application.product)
        prefix = NUMBER_PREFIX[product]
        sequence = self._policies.next_sequence(prefix, effective.year)
        return self._policies.add(
            policy_number=f"{prefix}-{effective.year:04d}-{sequence:06d}",
            product=product.value,
            application_id=application.id,
            customer_id=application.customer_id,
            rule_version=application.rule_version,
            rating_inputs=quote.inputs,
            sum_insured=quote.sum_insured,
            premium=quote.premium,
            effective_date=effective,
            expiry_date=expiry,
            premium_due_date=effective,
            status=PolicyStatus.ACTIVE,
            address=application.address,
        )
