"""AC-03 / AC-09: application and underwriting repositories on a temp SQLite database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.repository.application_repository import ApplicationRepository
from src.repository.quote_repository import QuoteRepository
from src.repository.underwriting_repository import (
    UnderwritingDecisionRepository,
    UnderwritingOverrideRepository,
)
from src.types.enums import ApplicationStatus, Decision


def _application(session: Session) -> str:
    quote = QuoteRepository(session).add(
        product="MOTOR",
        rule_version=1,
        inputs={"vehicle_age_years": 3},
        sum_insured=Decimal("500000.00"),
        premium=Decimal("14322.00"),
        breakdown={},
        actor_id="cust-001",
    )
    row = ApplicationRepository(session).add(
        quote_id=quote.id,
        customer_id="cust-001",
        product="MOTOR",
        rule_version=1,
        status=ApplicationStatus.MANUAL_REVIEW,
        status_history=["SUBMITTED", "UNDERWRITING", "MANUAL_REVIEW"],
        full_name="Test Customer 01",
        date_of_birth=date(1996, 4, 1),
        address="1 Sample Street, Testville",
        aadhaar_masked="XXXX-XXXX-0001",
        pan_masked="XXXXX0001X",
        risk_inputs={"vehicle_age_years": 3},
    )
    return row.id


@pytest.mark.ac("AC-03")
def test_ac03_application_repository_round_trips_and_transitions(seeded_session: Session) -> None:
    """AC-03: add, read back, list by status and transition appends to the history."""
    repo = ApplicationRepository(seeded_session)
    app_id = _application(seeded_session)
    row = repo.get(app_id)
    assert row is not None and row.aadhaar_masked == "XXXX-XXXX-0001"
    assert [r.id for r in repo.list_by_statuses([ApplicationStatus.MANUAL_REVIEW])] == [app_id]
    repo.transition(row, ApplicationStatus.AUTO_BIND)
    assert row.status == "AUTO_BIND"
    assert row.status_history[-1] == "AUTO_BIND"
    assert repo.list_by_statuses([ApplicationStatus.MANUAL_REVIEW]) == []
    assert repo.get("missing") is None


@pytest.mark.ac("AC-09")
def test_ac09_decision_and_override_repositories_append_and_read(seeded_session: Session) -> None:
    """AC-09: decisions and overrides are appended in order and read back per application."""
    app_id = _application(seeded_session)
    decisions = UnderwritingDecisionRepository(seeded_session)
    first = decisions.add(
        application_id=app_id,
        decision=Decision.DECLINE,
        reason_codes=["MO-UW-001"],
        product="MOTOR",
        rule_version=1,
        decided_by="SYSTEM",
        comment=None,
    )
    second = decisions.add(
        application_id=app_id,
        decision=Decision.AUTO_BIND,
        reason_codes=["MO-UW-901"],
        product="MOTOR",
        rule_version=1,
        decided_by="admin-001",
        comment="restored",
    )
    assert [d.id for d in decisions.list_for_application(app_id)] == [first.id, second.id]
    latest = decisions.latest_for_application(app_id)
    assert latest is not None and latest.id == second.id
    overrides = UnderwritingOverrideRepository(seeded_session)
    row = overrides.add(
        application_id=app_id,
        original_decision_id=first.id,
        reason_code="MO-UW-901",
        comment="Vehicle restored and certified",
        actor_id="admin-001",
    )
    assert [o.id for o in overrides.list_for_application(app_id)] == [row.id]
    assert overrides.list_for_application("other") == []
