"""Integration tests: the demo portfolio the seed builds through the services (E9-S3).

Every row here is produced by ``seed_portfolio`` driving the real quote, application,
underwriting, issuance, endorsement, payment, renewal, cancellation and end-of-day code, so
these assertions also prove those services compose (AC-02, AC-04, AC-05, NFR-03).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.repository.models import (
    Application,
    Endorsement,
    Policy,
    PolicyStateTransition,
    PremiumPayment,
    Refund,
    RuleSetVersion,
    UnderwritingDecision,
)
from src.seed import seed_portfolio
from src.types.enums import Decision, PolicyStatus, ProductCode, RuleSetStatus

pytestmark = pytest.mark.integration

_COUNTED = (
    RuleSetVersion,
    Application,
    UnderwritingDecision,
    Policy,
    PolicyStateTransition,
    Endorsement,
    PremiumPayment,
    Refund,
)
_REASON_CODE = re.compile(r"^(TL|MO|HH)-UW-\d{3}$")
_MASKED_AADHAAR = re.compile(r"^XXXX-XXXX-\d{4}$")
_MASKED_PAN = re.compile(r"^XXXXX\d{4}X$")
_RAW_PII = re.compile(r"\b9999\d{8}\b|AAAAA\d{4}A")


def _count(session: Session, model: type) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def _snapshot(session: Session) -> dict[str, int]:
    return {model.__name__: _count(session, model) for model in _COUNTED}


def _policies_by_status(session: Session) -> dict[str, int]:
    rows = session.execute(select(Policy.status, func.count()).group_by(Policy.status)).all()
    return {status: count for status, count in rows}


@pytest.fixture(name="portfolio")
def _portfolio(seeded_engine: Engine) -> Iterator[Session]:
    """A session on a database holding the three v1 rule sets *and* the demo portfolio."""
    with Session(seeded_engine) as session:
        seed_portfolio(session)
        yield session


@pytest.mark.ac("AC-02")
def test_ac02_three_products_are_published(portfolio: Session) -> None:
    rows = list(portfolio.execute(select(RuleSetVersion)).scalars())
    published = {row.product for row in rows if row.status == RuleSetStatus.PUBLISHED.value}
    assert published == {code.value for code in ProductCode}


@pytest.mark.ac("AC-04")
def test_ac04_at_least_seventy_percent_of_decisions_auto_bind(portfolio: Session) -> None:
    decisions = list(portfolio.execute(select(UnderwritingDecision)).scalars())
    assert len(decisions) >= 20
    by_decision = [row.decision for row in decisions]
    auto = by_decision.count(Decision.AUTO_BIND.value)
    assert auto / len(decisions) >= 0.70
    assert by_decision.count(Decision.MANUAL_REVIEW.value) >= 1
    assert by_decision.count(Decision.DECLINE.value) >= 1
    for row in decisions:
        if row.decision != Decision.AUTO_BIND.value:
            assert row.reason_codes
            assert all(_REASON_CODE.match(code) for code in row.reason_codes)


@pytest.mark.ac("AC-05")
def test_ac05_every_lifecycle_status_is_represented(portfolio: Session) -> None:
    counts = _policies_by_status(portfolio)
    for status in PolicyStatus:
        assert counts.get(status.value, 0) >= 1, f"no {status.value} policy: {counts}"


@pytest.mark.ac("AC-05")
def test_ac05_active_policies_cover_two_products(portfolio: Session) -> None:
    products = {
        row.product
        for row in portfolio.execute(select(Policy)).scalars()
        if row.status == PolicyStatus.ACTIVE.value
    }
    assert len(products) >= 2


@pytest.mark.ac("AC-05")
def test_ac05_every_policy_has_a_transition_and_a_first_premium_payment(
    portfolio: Session,
) -> None:
    for policy in portfolio.execute(select(Policy)).scalars():
        transitions = portfolio.execute(
            select(func.count())
            .select_from(PolicyStateTransition)
            .where(PolicyStateTransition.policy_id == policy.id)
        ).scalar_one()
        assert transitions >= 1, policy.policy_number
        if policy.previous_policy_number is not None:
            continue  # a renewal term is paid on its predecessor (conventions -> renewal)
        payments = portfolio.execute(
            select(func.count())
            .select_from(PremiumPayment)
            .where(PremiumPayment.policy_id == policy.id)
        ).scalar_one()
        assert payments >= 1, policy.policy_number


@pytest.mark.ac("AC-05")
def test_ac05_renewed_policy_has_a_successor_pointing_back(portfolio: Session) -> None:
    policies = list(portfolio.execute(select(Policy)).scalars())
    renewed = [row for row in policies if row.status == PolicyStatus.RENEWED.value]
    assert renewed
    by_previous = {row.previous_policy_number: row for row in policies}
    for row in renewed:
        successor = by_previous.get(row.policy_number)
        assert successor is not None, row.policy_number
        assert successor.status == PolicyStatus.ACTIVE.value
        assert successor.effective_date == row.expiry_date + timedelta(days=1)


@pytest.mark.ac("AC-05")
def test_ac05_endorsed_policy_has_an_endorsement_row(portfolio: Session) -> None:
    endorsed = [
        row
        for row in portfolio.execute(select(Policy)).scalars()
        if row.status == PolicyStatus.ENDORSED.value
    ]
    assert endorsed
    for row in endorsed:
        count = portfolio.execute(
            select(func.count()).select_from(Endorsement).where(Endorsement.policy_id == row.id)
        ).scalar_one()
        assert count == 1, row.policy_number


@pytest.mark.ac("AC-05")
def test_ac05_cancelled_policy_has_exactly_one_refund(portfolio: Session) -> None:
    cancelled = [
        row
        for row in portfolio.execute(select(Policy)).scalars()
        if row.status == PolicyStatus.CANCELLED.value
    ]
    assert cancelled
    for row in cancelled:
        count = portfolio.execute(
            select(func.count()).select_from(Refund).where(Refund.policy_id == row.id)
        ).scalar_one()
        assert count == 1, row.policy_number


def test_seeded_personal_data_is_masked_and_synthetic(portfolio: Session) -> None:
    applications = list(portfolio.execute(select(Application)).scalars())
    assert applications
    for row in applications:
        assert _MASKED_AADHAAR.match(row.aadhaar_masked), row.aadhaar_masked
        assert _MASKED_PAN.match(row.pan_masked), row.pan_masked
        assert row.full_name.startswith("Test Customer ")
        assert not _RAW_PII.search(f"{row.aadhaar_masked}{row.pan_masked}{row.address}")


@pytest.mark.ac("AC-02")
def test_ac02_second_seed_run_inserts_nothing(portfolio: Session) -> None:
    before = _snapshot(portfolio)
    summary = seed_portfolio(portfolio)
    assert _snapshot(portfolio) == before
    assert summary.inserted is False
