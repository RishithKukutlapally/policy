"""Integration tests of the insert-only quote repository."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.repository.quote_repository import QuoteRepository


@pytest.mark.ac("AC-13")
def test_ac13_quote_round_trips_with_decimal_precision(seeded_session: Session) -> None:
    """AC-13: money reads back as Decimal, breakdown and inputs survive."""
    repository = QuoteRepository(seeded_session)
    added = repository.add(
        product="MOTOR",
        rule_version=1,
        inputs={"sum_insured": "500000.00"},
        sum_insured=Decimal("500000.00"),
        premium=Decimal("14322.00"),
        breakdown={"final_amount": "14322.00"},
        actor_id="cust-001",
    )
    seeded_session.commit()
    seeded_session.expire_all()
    row = repository.get(added.id)
    assert row is not None
    assert type(row.premium) is Decimal
    assert row.premium == Decimal("14322.00")
    assert row.breakdown == {"final_amount": "14322.00"}
    assert repository.get("missing") is None


@pytest.mark.ac("AC-13")
def test_ac13_repository_is_insert_only() -> None:
    """AC-13: no update or delete surface."""
    names = {n for n in dir(QuoteRepository) if not n.startswith("_")}
    assert names == {"add", "get"}
