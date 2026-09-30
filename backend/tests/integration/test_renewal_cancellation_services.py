"""Service-level tests: payments, renewal, cancellation and the end-of-day job (AC-07/08/17/18)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.jobs import end_of_day
from src.repository.models import AuditRecord, PolicyStateTransition, PremiumPayment, Refund
from src.repository.policy_lifecycle_repository import PolicyStateTransitionRepository
from src.service.cancellation_service import CancellationService
from src.service.payment_service import PaymentService
from src.service.renewal_service import RenewalService
from src.types.enums import ActorRole
from src.types.errors import (
    InvalidPolicyStateException,
    NotFoundError,
    OutsideRenewalWindowError,
    PremiumAlreadyPaidError,
    ValidationError,
)
from tests.renewal_helpers import IN_WINDOW, count, issue_policy, pay, status_of

pytestmark = pytest.mark.ac("AC-08")


class _Actor:
    def __init__(self, actor_id: str = "cust-001", role: ActorRole = ActorRole.CUSTOMER) -> None:
        self.actor_id = actor_id
        self.role = role


def test_ac08_preview_persists_nothing(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """preview returns the breakdown and leaves refunds, transitions and status untouched."""
    number = issue_policy(api_client, monkeypatch)
    before = count(seeded_engine, PolicyStateTransition)
    with Session(seeded_engine) as session:
        view = CancellationService(session).preview(number, date(2026, 6, 1), _Actor())
    assert view.amount == Decimal("11343.15")
    assert view.gross_refund == Decimal("11593.15")
    assert view.admin_fee == Decimal("250.00")
    assert count(seeded_engine, Refund) == 0
    assert count(seeded_engine, PolicyStateTransition) == before
    assert status_of(seeded_engine, number) == "ACTIVE"


def test_ac08_cancel_is_atomic_when_transition_insert_fails(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing transition insert leaves no refund row and the status unchanged."""
    number = issue_policy(api_client, monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("transition insert failed")

    monkeypatch.setattr(PolicyStateTransitionRepository, "add", boom)
    with Session(seeded_engine) as session, pytest.raises(RuntimeError):
        CancellationService(session).cancel(number, date(2026, 6, 1), "Vehicle sold", _Actor())
    assert count(seeded_engine, Refund) == 0
    assert status_of(seeded_engine, number) == "ACTIVE"


def test_ac08_cancel_terminal_and_unknown_policy(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Terminal -> InvalidPolicyStateException; another customer's / unknown -> NotFoundError."""
    number = issue_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        service = CancellationService(session)
        service.cancel(number, date(2026, 6, 1), "Vehicle sold", _Actor())
        with pytest.raises(InvalidPolicyStateException):
            service.cancel(number, date(2026, 6, 1), "again", _Actor())
        with pytest.raises(InvalidPolicyStateException):
            service.preview(number, date(2026, 6, 1), _Actor())
        with pytest.raises(NotFoundError):
            service.preview(number, date(2026, 6, 1), _Actor("cust-002"))
        with pytest.raises(NotFoundError):
            service.preview("MO-2026-999999", date(2026, 6, 1), _Actor())


@pytest.mark.ac("AC-17")
def test_ac17_payment_service_validation(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad amounts, early payments and duplicates raise typed errors and persist nothing."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "2026-12-01")
    before = count(seeded_engine, PremiumPayment)
    with Session(seeded_engine) as session, pytest.raises(OutsideRenewalWindowError):
        PaymentService(session).record_payment(number, Decimal("15500.00"), _Actor())
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    with Session(seeded_engine) as session:
        service = PaymentService(session)
        for bad in ("0.00", "-1.00", "100.005"):
            with pytest.raises(ValidationError):
                service.record_payment(number, Decimal(bad), _Actor())
        with pytest.raises(ValidationError) as mismatch:
            service.record_payment(number, Decimal("10000.00"), _Actor())
        assert mismatch.value.details == [{"field": "amount", "code": "AMOUNT_MISMATCH"}]
        assert count(seeded_engine, PremiumPayment) == before
        record = service.record_payment(number, Decimal("15500.00"), _Actor())
        assert record.amount == Decimal("15500.00")
        with pytest.raises(PremiumAlreadyPaidError):
            service.record_payment(number, Decimal("15500.00"), _Actor())
    assert count(seeded_engine, PremiumPayment) == before + 1


@pytest.mark.ac("AC-07")
def test_ac07_renewal_service_quote_and_terminal_state(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The quote carries Decimal money; a terminal policy cannot be quoted."""
    number = issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    with Session(seeded_engine) as session:
        quote = RenewalService(session).renewal_quote(number, _Actor())
        assert quote.renewal_premium == Decimal("15500.00")
        assert quote.due_date == date(2027, 3, 1)
        assert quote.grace_end_date == date(2027, 3, 31)
        assert quote.renewal_window_opens == date(2027, 1, 29)
        CancellationService(session).cancel(number, date(2027, 2, 15), "Vehicle sold", _Actor())
        with pytest.raises(InvalidPolicyStateException):
            RenewalService(session).renewal_quote(number, _Actor())


@pytest.mark.ac("AC-18")
def test_ac18_cli_job_uses_system_actor_and_is_idempotent(
    api_client: TestClient,
    seeded_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`python -m src.jobs.end_of_day --as-of` runs as system-eod and re-runs to zero."""
    paid = issue_policy(api_client, monkeypatch)
    issue_policy(api_client, monkeypatch)
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", IN_WINDOW)
    assert pay(api_client, paid).status_code == 201
    monkeypatch.setattr(end_of_day, "SessionLocal", sessionmaker(bind=seeded_engine))
    assert end_of_day.main(["--as-of", "2027-04-01"]) == 0
    first = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (first["renewed"], first["lapsed"]) == (1, 1)
    assert end_of_day.main(["--as-of", "2027-04-01"]) == 0
    second = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (second["renewed"], second["lapsed"]) == (0, 0)
    with Session(seeded_engine) as session:
        rows = session.query(AuditRecord).filter_by(action="RUN_END_OF_DAY").all()
        assert [(r.actor_id, r.actor_role) for r in rows] == [("system-eod", "SYSTEM")] * 2
        actors = {t.actor_id for t in session.query(PolicyStateTransition).all()}
        assert "system-eod" in actors
    assert end_of_day.main(["--as-of", "not-a-date"]) == 2
