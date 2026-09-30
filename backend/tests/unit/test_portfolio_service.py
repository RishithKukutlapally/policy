"""Unit tests for :mod:`src.service.portfolio_service` (E9-S1, AC-20, NFR-01).

Covers the empty book (zeros, never ``None``), the ``as_of`` collection boundary and the money
contract: every amount is a :class:`~decimal.Decimal` quantized to exactly two places.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.service.portfolio_service import PortfolioService
from src.types.enums import PolicyStatus, ProductCode
from tests.portfolio_helpers import AS_OF, FakeActor, seed_payment, seed_policy

_ZERO = Decimal("0.00")


def _portfolio(session: Session, as_of: date = AS_OF) -> object:
    """Report the portfolio of ``session`` on ``as_of`` as the demo admin."""
    return PortfolioService(session).portfolio(as_of, FakeActor())


def test_empty_portfolio_returns_zeros_and_no_pipeline(seeded_session: Session) -> None:
    """An empty book reports zeros for every product and money figure, never ``None``."""
    view = _portfolio(seeded_session)
    assert view.active_by_product == {"TERM_LIFE": 0, "MOTOR": 0, "HOUSEHOLD": 0}
    assert view.sum_insured_by_product == {"TERM_LIFE": _ZERO, "MOTOR": _ZERO, "HOUSEHOLD": _ZERO}
    assert view.premium_collected == _ZERO
    assert view.refunds_paid == _ZERO
    assert view.renewal_pipeline == ()
    assert view.lapse_forecast.count == 0
    assert view.lapse_forecast.premium_at_risk == _ZERO
    assert view.lapse_forecast.policies == ()
    assert view.as_of == AS_OF


def _policy_with_two_payments(session: Session) -> None:
    """Seed one policy paid on ``AS_OF`` and once again the day after."""
    policy = seed_policy(
        session,
        policy_number="MO-2026-000009",
        product=ProductCode.MOTOR,
        status=PolicyStatus.ACTIVE,
        sum_insured=Decimal("400000.00"),
        premium=Decimal("15500.00"),
        effective_date=date(2026, 6, 1),
        expiry_date=date(2027, 5, 31),
    )
    seed_payment(
        session,
        policy,
        due_date=date(2026, 6, 1),
        amount=Decimal("15500.00"),
        collected_on=AS_OF,
    )
    seed_payment(
        session,
        policy,
        due_date=date(2027, 6, 1),
        amount=Decimal("777.77"),
        collected_on=AS_OF + timedelta(days=1),
    )
    session.commit()


def test_as_of_boundary_includes_the_day_itself_only(seeded_session: Session) -> None:
    """A payment collected on ``as_of`` counts; one collected the day after does not."""
    _policy_with_two_payments(seeded_session)
    assert _portfolio(seeded_session).premium_collected == Decimal("15500.00")
    later = _portfolio(seeded_session, AS_OF + timedelta(days=1))
    assert later.premium_collected == Decimal("16277.77")


def test_money_is_decimal_with_two_decimal_places(seeded_session: Session) -> None:
    """Every money figure is a ``Decimal`` with exponent ``-2`` — no floats anywhere (NFR-01)."""
    _policy_with_two_payments(seeded_session)
    view = _portfolio(seeded_session)
    amounts = [
        view.premium_collected,
        view.refunds_paid,
        view.lapse_forecast.premium_at_risk,
        *view.sum_insured_by_product.values(),
    ]
    for amount in amounts:
        assert isinstance(amount, Decimal)
        assert amount.as_tuple().exponent == -2
