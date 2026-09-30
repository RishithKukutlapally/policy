"""Renewal router - endpoints 2.20 to 2.22 of `specs/design/api-contracts.md` (AC-07, AC-17).

The quote is open to the owning CUSTOMER and ADMIN; renew and payments are owner-only.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.policies import PolicySummaryResponse
from src.api.schemas.renewals import PaymentRequest, PaymentResponse, RenewalQuoteResponse
from src.service.payment_service import PaymentService
from src.service.renewal_service import RenewalService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole

router = APIRouter(prefix="/policies", tags=["renewals"])

CustomerActor = Annotated[Actor, Depends(require_role(ActorRole.CUSTOMER))]
QuoteActor = Annotated[Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.ADMIN))]
ServiceSession = Annotated[Session, Depends(get_service_session)]


@router.get("/{policy_number}/renewal", summary="Renewal quote")
def renewal_quote(
    policy_number: str, actor: QuoteActor, session: ServiceSession
) -> RenewalQuoteResponse:
    """Contract 2.20 - refreshed premium on the active version, with due and grace dates."""
    view = RenewalService(session).renewal_quote(policy_number, actor)
    return RenewalQuoteResponse.from_view(view)


@router.post("/{policy_number}/renew", status_code=201, summary="Renew a policy")
def renew_policy(
    policy_number: str, actor: CustomerActor, session: ServiceSession
) -> PolicySummaryResponse:
    """Contract 2.21 - successor term created, old policy RENEWED, in one transaction."""
    return PolicySummaryResponse.from_view(RenewalService(session).renew(policy_number, actor))


@router.post("/{policy_number}/payments", status_code=201, summary="Pay the renewal premium")
def record_payment(
    policy_number: str, body: PaymentRequest, actor: CustomerActor, session: ServiceSession
) -> PaymentResponse:
    """Contract 2.22 - appends one immutable premium payment."""
    record = PaymentService(session).record_payment(policy_number, body.to_decimal(), actor)
    return PaymentResponse.from_record(record)
