"""Unit tests of the quote service against a seeded temp database."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.deps import Actor
from src.repository.models import Quote
from src.service.quote_service import QuoteService, QuoteValidationError
from src.types.enums import ActorRole, ProductCode
from src.types.errors import NotFoundError
from tests.quote_helpers import MOTOR_INPUTS

CUSTOMER = Actor("cust-001", ActorRole.CUSTOMER)
OTHER = Actor("cust-002", ActorRole.CUSTOMER)
STAFF = Actor("uw-001", ActorRole.UNDERWRITER)


@pytest.mark.ac("AC-01")
def test_ac01_create_quote_persists_decimal_premium_and_breakdown(seeded_session: Session) -> None:
    """AC-01: the row keeps Decimal money, the version and the breakdown."""
    service = QuoteService(seeded_session)
    quote = service.create_quote(ProductCode.MOTOR, dict(MOTOR_INPUTS), CUSTOMER)
    row = seeded_session.get(Quote, quote.id)
    assert row is not None
    assert row.premium == Decimal("14322.00")
    assert type(row.premium) is Decimal
    assert row.rule_version == 1
    assert row.breakdown["final_amount"] == "14322.00"
    assert row.actor_id == "cust-001"


@pytest.mark.ac("AC-12")
def test_ac12_validation_error_lists_fields_and_persists_nothing(seeded_session: Session) -> None:
    """AC-12: missing sum_insured -> REQUIRED, nothing stored."""
    inputs = {k: v for k, v in MOTOR_INPUTS.items() if k != "sum_insured"}
    with pytest.raises(QuoteValidationError) as caught:
        QuoteService(seeded_session).create_quote(ProductCode.MOTOR, inputs, CUSTOMER)
    assert {"field": "sum_insured", "code": "REQUIRED"} in (caught.value.details or [])
    assert seeded_session.execute(select(func.count()).select_from(Quote)).scalar() == 0


@pytest.mark.ac("AC-13")
def test_ac13_get_quote_ownership_is_404_for_other_customer(seeded_session: Session) -> None:
    """AC-13: another customer's quote is NOT_FOUND; staff may read it."""
    service = QuoteService(seeded_session)
    quote = service.create_quote(ProductCode.MOTOR, dict(MOTOR_INPUTS), CUSTOMER)
    assert service.get_quote(quote.id, STAFF).id == quote.id
    with pytest.raises(NotFoundError):
        service.get_quote(quote.id, OTHER)
    with pytest.raises(NotFoundError):
        service.reprice(quote.id, OTHER)


@pytest.mark.ac("AC-13")
def test_ac13_reprice_reproduces_stored_premium(seeded_session: Session) -> None:
    """AC-13: reprice returns the identical Decimal premium."""
    service = QuoteService(seeded_session)
    quote = service.create_quote(ProductCode.MOTOR, dict(MOTOR_INPUTS), CUSTOMER)
    result = service.reprice(quote.id, CUSTOMER)
    assert result.recomputed_premium == result.stored_premium == Decimal("14322.00")
    assert result.matches is True
