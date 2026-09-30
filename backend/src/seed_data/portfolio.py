"""Builds the demo portfolio by driving the production services (AC-02, AC-04, AC-05).

No row is inserted directly: every quote, application, decision, policy, endorsement, payment,
refund and state transition comes from the same service the API calls, so the seeded database is
internally consistent. Each phase pins the business date (:mod:`src.seed_data.timeline`) so the
RENEWED and LAPSED terms land on fixed, reproducible dates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.jobs.end_of_day import EndOfDayRunner
from src.repository.models import Application
from src.seed_data.actors import SeedActor, admin, customer, system
from src.seed_data.cases import CASES, CUSTOMER_COUNT, SeedCase, kyc_for
from src.seed_data.summary import PortfolioSummary, summarise
from src.seed_data.timeline import (
    CANCELLATION_DATE,
    DEMO_DATE,
    END_OF_DAY_DATE,
    LAPSE_TERM_START,
    RENEWAL_TERM_START,
    business_date,
)
from src.service.application_service import ApplicationService
from src.service.cancellation_service import CancellationService
from src.service.endorsement_service import EndorsementService
from src.service.payment_service import PaymentService
from src.service.policy_service import PolicyService
from src.service.quote_service import QuoteService
from src.service.renewal_service import RenewalService
from src.types.enums import EndorsementType

#: Address the ENDORSED showcase policy is moved to.
ENDORSED_ADDRESS: Final = "42 Sample Street, Testville 560002"
#: Reason recorded on the CANCELLED showcase policy's refund row.
CANCELLATION_REASON: Final = "Free-look cancellation requested by the customer"


@dataclass(frozen=True, slots=True)
class _Submitted:
    """One submitted case and the actor that owns it."""

    case: SeedCase
    application_id: str
    status: str
    actor: SeedActor


def _owner(case: SeedCase, position: int) -> SeedActor:
    """``cust-001`` owns the lifecycle showcase; ordinary cases spread over the demo customers."""
    return customer(1) if case.lifecycle else customer(position % CUSTOMER_COUNT + 1)


def _submit(session: Session, case: SeedCase, position: int) -> _Submitted:
    """Quote and apply for one case through the quote and application services."""
    actor = _owner(case, position)
    quote = QuoteService(session).create_quote(case.product, case.inputs, actor)
    view = ApplicationService(session).submit(
        quote.id, kyc_for(position + 1), case.health_declaration, actor
    )
    return _Submitted(case, view.id, view.status, actor)


def _issue(session: Session, submitted: _Submitted) -> str:
    """Issue the policy of an ``AUTO_BIND`` application and return its policy number."""
    return PolicyService(session).issue(submitted.application_id, submitted.actor).policy_number


def _endorse(session: Session, number: str) -> None:
    """Move the showcase policy to ENDORSED with an audited address change (AC-06)."""
    EndorsementService(session).apply(
        number, EndorsementType.CHANGE_ADDRESS, {"address": ENDORSED_ADDRESS}, admin()
    )


def _renew(session: Session, number: str, actor: SeedActor) -> None:
    """Pay the renewal premium due today, then renew — leaving RENEWED plus its successor."""
    quote = RenewalService(session).renewal_quote(number, actor)
    if quote.renewal_premium is None:  # pragma: no cover - v1 inputs always stay eligible
        raise RuntimeError(f"{number} is not renewable on the demo business date")
    PaymentService(session).record_payment(number, quote.renewal_premium, actor)
    RenewalService(session).renew(number, actor)


def _cancel(session: Session, number: str) -> None:
    """Cancel inside the free-look window, appending exactly one refund row (AC-08)."""
    CancellationService(session).cancel(number, CANCELLATION_DATE, CANCELLATION_REASON, admin())


def _lapse(session: Session) -> None:
    """Run end-of-day past the grace end of the unpaid term, lapsing it (AC-07, AC-18)."""
    with business_date(END_OF_DAY_DATE):
        EndOfDayRunner(session).run(END_OF_DAY_DATE, system())


def _already_seeded(session: Session) -> bool:
    """True once any application exists — the portfolio is built exactly once."""
    return session.execute(select(Application.id).limit(1)).first() is not None


def _positions_by_label(label: str) -> tuple[int, ...]:
    """Positions in :data:`CASES` whose ``lifecycle`` label is ``label``."""
    return tuple(index for index, case in enumerate(CASES) if case.lifecycle == label)


def _seed_back_dated_terms(session: Session) -> tuple[str, str]:
    """Issue the two terms that started in the past; returns (lapse, renewal) policy numbers."""
    with business_date(LAPSE_TERM_START):
        position = _positions_by_label("lapse")[0]
        lapse = _issue(session, _submit(session, CASES[position], position))
    with business_date(RENEWAL_TERM_START):
        position = _positions_by_label("renewal")[0]
        renewal = _issue(session, _submit(session, CASES[position], position))
    return lapse, renewal


def _seed_current_terms(session: Session, renewal_number: str) -> None:
    """Everything that happens on the demo business date: new business and lifecycle actions."""
    back_dated = set(_positions_by_label("lapse") + _positions_by_label("renewal"))
    with business_date(DEMO_DATE):
        issued: dict[str, list[str]] = {}
        for position, case in enumerate(CASES):
            if position in back_dated:
                continue
            submitted = _submit(session, case, position)
            if case.lifecycle:
                issued.setdefault(case.lifecycle, []).append(_issue(session, submitted))
        _endorse(session, issued["endorse"][0])
        _cancel(session, issued["cancel"][0])
        _renew(session, renewal_number, customer(1))


def seed_portfolio(session: Session) -> PortfolioSummary:
    """Build the demo portfolio once; a repeat call inserts nothing and only re-reads counts."""
    if _already_seeded(session):
        return summarise(session, inserted=False)
    _, renewal_number = _seed_back_dated_terms(session)
    _seed_current_terms(session, renewal_number)
    _lapse(session)
    return summarise(session, inserted=True)
