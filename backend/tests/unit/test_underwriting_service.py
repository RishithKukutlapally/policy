"""AC-14 / AC-09: service-level rules of the underwriting service."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from src.service.application_service import ApplicationService
from src.service.underwriting_service import UnderwritingService
from src.types.enums import ActorRole
from src.types.errors import ForbiddenError, NotFoundError, ValidationError


@dataclass(frozen=True)
class _Actor:
    actor_id: str
    role: ActorRole


UW = _Actor("uw-001", ActorRole.UNDERWRITER)
ADMIN = _Actor("admin-001", ActorRole.ADMIN)
CUSTOMER = _Actor("cust-001", ActorRole.CUSTOMER)


@pytest.mark.ac("AC-14")
def test_ac14_queue_rejects_customers_and_unknown_status(seeded_session: Session) -> None:
    """AC-14: CUSTOMER -> Forbidden; UNDERWRITER + DECLINED -> Forbidden; bad status -> 422."""
    service = UnderwritingService(seeded_session)
    with pytest.raises(ForbiddenError):
        service.queue(None, CUSTOMER)
    with pytest.raises(ForbiddenError):
        service.queue("DECLINED", UW)
    with pytest.raises(ValidationError):
        service.queue("ISSUED", ADMIN)
    assert service.queue(None, ADMIN) == []


@pytest.mark.ac("AC-14")
def test_ac14_unknown_application_is_not_found(seeded_session: Session) -> None:
    """AC-14: decide, override, audit and get on an unknown id -> NotFound."""
    service = UnderwritingService(seeded_session)
    with pytest.raises(NotFoundError):
        service.decide("nope", "APPROVE", ["MO-UW-900"], None, UW)
    with pytest.raises(NotFoundError):
        service.override("nope", "MO-UW-901", "a long enough comment", ADMIN)
    with pytest.raises(NotFoundError):
        service.audit_trail("nope", UW)
    with pytest.raises(NotFoundError):
        ApplicationService(seeded_session).get("nope", CUSTOMER)


@pytest.mark.ac("AC-09")
def test_ac09_override_is_admin_only_in_the_service(seeded_session: Session) -> None:
    """AC-09: defence in depth - a non-admin actor is refused before any lookup."""
    with pytest.raises(ForbiddenError):
        UnderwritingService(seeded_session).override("nope", "MO-UW-901", "long enough text", UW)
