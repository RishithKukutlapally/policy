"""AC-20: the admin portfolio dashboard reports exact Decimal figures for an explicit ``as_of``.

Every expected amount below is computed here with :mod:`decimal` from the seeded rows, so the test
fails if the service recomputes premiums instead of reading the stored values (NFR-01). Role
enforcement lives at the API layer (NFR-04, AC-22).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.service.portfolio_service import PortfolioService, PortfolioView
from src.types.enums import ActorRole, PolicyStatus, ProductCode
from tests.conftest import actor_headers
from tests.portfolio_helpers import (
    AS_OF,
    FakeActor,
    seed_payment,
    seed_policy,
    seed_refund,
)

pytestmark = pytest.mark.ac("AC-20")

_TERM_LIFE_FIRST = Decimal("12000.00")
_MOTOR_RENEWING_FIRST = Decimal("15500.00")
_MOTOR_RENEWING_RENEWAL = Decimal("15500.00")
_MOTOR_UNPAID_FIRST = Decimal("9000.00")
_HOUSEHOLD_FIRST = Decimal("3100.00")
_MOTOR_LAPSING_FIRST = Decimal("4200.00")
_MOTOR_CANCELLED_FIRST = Decimal("8000.00")
_TERM_LIFE_LAPSED_FIRST = Decimal("6000.00")
_REFUND = Decimal("4000.00")

_EXPECTED_COLLECTED = (
    _TERM_LIFE_FIRST
    + _MOTOR_RENEWING_FIRST
    + _MOTOR_RENEWING_RENEWAL
    + _MOTOR_UNPAID_FIRST
    + _HOUSEHOLD_FIRST
    + _MOTOR_LAPSING_FIRST
    + _MOTOR_CANCELLED_FIRST
    + _TERM_LIFE_LAPSED_FIRST
).quantize(Decimal("0.01"))

_EXPECTED_MOTOR_SUM_INSURED = (
    Decimal("400000.00") + Decimal("500000.00") + Decimal("300000.00")
).quantize(Decimal("0.01"))


def _seed_portfolio(session: Session) -> None:
    """Seed the deterministic portfolio the assertions below are computed from."""
    term_life = seed_policy(
        session,
        policy_number="TL-2026-000001",
        product=ProductCode.TERM_LIFE,
        status=PolicyStatus.ACTIVE,
        sum_insured=Decimal("1000000.00"),
        premium=_TERM_LIFE_FIRST,
        effective_date=date(2026, 4, 1),
        expiry_date=date(2027, 3, 31),
    )
    seed_payment(session, term_life, due_date=date(2026, 4, 1), amount=_TERM_LIFE_FIRST)

    renewing = seed_policy(
        session,
        policy_number="MO-2026-000001",
        product=ProductCode.MOTOR,
        status=PolicyStatus.ACTIVE,
        sum_insured=Decimal("400000.00"),
        premium=_MOTOR_RENEWING_FIRST,
        effective_date=date(2026, 1, 16),
        expiry_date=date(2027, 1, 14),
    )
    seed_payment(session, renewing, due_date=date(2026, 1, 16), amount=_MOTOR_RENEWING_FIRST)
    seed_payment(session, renewing, due_date=date(2027, 1, 15), amount=_MOTOR_RENEWING_RENEWAL)

    unpaid = seed_policy(
        session,
        policy_number="MO-2026-000002",
        product=ProductCode.MOTOR,
        status=PolicyStatus.ENDORSED,
        sum_insured=Decimal("500000.00"),
        premium=_MOTOR_UNPAID_FIRST,
        effective_date=date(2026, 1, 21),
        expiry_date=date(2027, 1, 19),
    )
    seed_payment(session, unpaid, due_date=date(2026, 1, 21), amount=_MOTOR_UNPAID_FIRST)

    household = seed_policy(
        session,
        policy_number="HH-2026-000001",
        product=ProductCode.HOUSEHOLD,
        status=PolicyStatus.ACTIVE,
        sum_insured=Decimal("2000000.00"),
        premium=_HOUSEHOLD_FIRST,
        effective_date=date(2026, 3, 2),
        expiry_date=date(2027, 3, 1),
    )
    seed_payment(session, household, due_date=date(2026, 3, 2), amount=_HOUSEHOLD_FIRST)

    _seed_terminal_and_lapsing(session)
    session.commit()


def _seed_terminal_and_lapsing(session: Session) -> None:
    """Seed the in-grace motor policy plus one CANCELLED (with refund) and one LAPSED policy."""
    lapsing = seed_policy(
        session,
        policy_number="MO-2025-000003",
        product=ProductCode.MOTOR,
        status=PolicyStatus.ACTIVE,
        sum_insured=Decimal("300000.00"),
        premium=_MOTOR_LAPSING_FIRST,
        effective_date=date(2025, 12, 21),
        expiry_date=date(2026, 12, 19),
    )
    seed_payment(session, lapsing, due_date=date(2025, 12, 21), amount=_MOTOR_LAPSING_FIRST)

    cancelled = seed_policy(
        session,
        policy_number="MO-2026-000004",
        product=ProductCode.MOTOR,
        status=PolicyStatus.CANCELLED,
        sum_insured=Decimal("250000.00"),
        premium=_MOTOR_CANCELLED_FIRST,
        effective_date=date(2026, 6, 1),
        expiry_date=date(2027, 5, 31),
    )
    seed_payment(session, cancelled, due_date=date(2026, 6, 1), amount=_MOTOR_CANCELLED_FIRST)
    seed_refund(
        session,
        cancelled,
        premium_paid=_MOTOR_CANCELLED_FIRST,
        amount=_REFUND,
        term_days=365,
        days_elapsed=92,
        admin_fee=Decimal("250.00"),
        cancellation_date=date(2026, 9, 1),
    )

    lapsed = seed_policy(
        session,
        policy_number="TL-2026-000002",
        product=ProductCode.TERM_LIFE,
        status=PolicyStatus.LAPSED,
        sum_insured=Decimal("500000.00"),
        premium=_TERM_LIFE_LAPSED_FIRST,
        effective_date=date(2025, 11, 2),
        expiry_date=date(2026, 11, 1),
    )
    seed_payment(session, lapsed, due_date=date(2025, 11, 2), amount=_TERM_LIFE_LAPSED_FIRST)


@pytest.fixture(name="portfolio")
def _portfolio(seeded_session: Session) -> PortfolioView:
    """The portfolio view of the seeded book, reported on :data:`AS_OF`."""
    _seed_portfolio(seeded_session)
    return PortfolioService(seeded_session).portfolio(AS_OF, FakeActor())


def test_ac20_active_counts_and_sum_insured_by_product(portfolio: PortfolioView) -> None:
    """AC-20: in-force counts and sum insured list all three products; terminal policies are out."""
    assert portfolio.active_by_product == {"TERM_LIFE": 1, "MOTOR": 3, "HOUSEHOLD": 1}
    assert portfolio.sum_insured_by_product == {
        "TERM_LIFE": Decimal("1000000.00"),
        "MOTOR": _EXPECTED_MOTOR_SUM_INSURED,
        "HOUSEHOLD": Decimal("2000000.00"),
    }


def test_ac20_cancelled_and_lapsed_are_not_in_force(portfolio: PortfolioView) -> None:
    """AC-20: a CANCELLED and a LAPSED policy are excluded from every in-force figure."""
    numbers = {item.policy_number for item in portfolio.renewal_pipeline}
    numbers |= {item.policy_number for item in portfolio.lapse_forecast.policies}
    assert "MO-2026-000004" not in numbers
    assert "TL-2026-000002" not in numbers
    # 5 in-force rows out of the 7 seeded.
    assert sum(portfolio.active_by_product.values()) == 5


def test_ac20_premium_collected_and_refunds_paid(portfolio: PortfolioView) -> None:
    """AC-20: money is the sum of the stored payment and refund rows, quantized to two places."""
    assert portfolio.premium_collected == _EXPECTED_COLLECTED
    assert portfolio.refunds_paid == _REFUND
    for amount in (portfolio.premium_collected, portfolio.refunds_paid):
        assert isinstance(amount, Decimal)
        assert amount.as_tuple().exponent == -2


def test_ac20_renewal_pipeline_inside_the_window(portfolio: PortfolioView) -> None:
    """AC-20: the pipeline holds only renewals due in ``(as_of, as_of + 30]`` with paid flags."""
    pipeline = portfolio.renewal_pipeline
    assert [(item.policy_number, item.due_date, item.paid) for item in pipeline] == [
        ("MO-2026-000001", date(2027, 1, 15), True),
        ("MO-2026-000002", date(2027, 1, 20), False),
    ]
    assert pipeline[0].renewal_premium == _MOTOR_RENEWING_RENEWAL
    assert pipeline[1].renewal_premium == _MOTOR_UNPAID_FIRST
    assert all(item.product == "MOTOR" for item in pipeline)


def test_ac20_lapse_forecast_projects_the_grace_end(portfolio: PortfolioView) -> None:
    """AC-20: the forecast holds the unpaid in-grace policy with its projected lapse date."""
    forecast = portfolio.lapse_forecast
    assert forecast.count == 1
    assert forecast.premium_at_risk == _MOTOR_LAPSING_FIRST
    only = forecast.policies[0]
    assert only.policy_number == "MO-2025-000003"
    assert only.product == "MOTOR"
    assert only.due_date == date(2026, 12, 20)
    assert only.grace_end_date == date(2027, 1, 19)
    assert only.premium == _MOTOR_LAPSING_FIRST


def test_ac20_endpoint_serialises_money_as_strings(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-20: ADMIN gets 200 with money as two-decimal strings for the requested ``as_of``."""
    with Session(seeded_engine) as session:
        _seed_portfolio(session)
    response = api_client.get(
        "/api/admin/portfolio",
        params={"as_of": AS_OF.isoformat()},
        headers=actor_headers(ActorRole.ADMIN),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["as_of"] == "2027-01-01"
    assert body["active_by_product"] == {"TERM_LIFE": 1, "MOTOR": 3, "HOUSEHOLD": 1}
    assert body["premium_collected"] == str(_EXPECTED_COLLECTED)
    assert body["refunds_paid"] == "4000.00"
    assert [item["policy_number"] for item in body["renewal_pipeline"]] == [
        "MO-2026-000001",
        "MO-2026-000002",
    ]
    assert body["lapse_forecast"]["count"] == 1
    assert body["lapse_forecast"]["premium_at_risk"] == "4200.00"
    assert body["lapse_forecast"]["policies"][0]["grace_end_date"] == "2027-01-19"


@pytest.mark.parametrize("role", [ActorRole.CUSTOMER, ActorRole.UNDERWRITER])
def test_ac20_non_admin_is_forbidden(api_client: TestClient, role: ActorRole) -> None:
    """AC-20: CUSTOMER and UNDERWRITER get 403 FORBIDDEN on the portfolio endpoint (NFR-04)."""
    response = api_client.get("/api/admin/portfolio", headers=actor_headers(role))
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_ac20_missing_actor_headers_are_unauthenticated(api_client: TestClient) -> None:
    """AC-20: without the actor headers the endpoint answers 401 UNAUTHENTICATED (NFR-04)."""
    response = api_client.get("/api/admin/portfolio")
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_ac20_malformed_as_of_is_a_validation_error(api_client: TestClient) -> None:
    """AC-20: a malformed ``as_of`` answers 422 VALIDATION_ERROR / INVALID_FORMAT."""
    response = api_client.get(
        "/api/admin/portfolio",
        params={"as_of": "2027-13-01"},
        headers=actor_headers(ActorRole.ADMIN),
    )
    assert response.status_code == 422, response.text
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"] == [{"field": "as_of", "code": "INVALID_FORMAT"}]
