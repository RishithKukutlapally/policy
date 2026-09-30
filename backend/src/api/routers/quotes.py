"""Quote router - endpoints 2.7 to 2.9 of `specs/design/api-contracts.md` (AC-01, AC-12, AC-13).

POST is CUSTOMER only; reads are open to the owner, UNDERWRITER and ADMIN (owner scoping is done
by the service, which answers 404 for another customer's quote).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.quotes import (
    QuoteDetailResponse,
    QuoteRequest,
    QuoteResponse,
    RepriceResponse,
)
from src.service.quote_service import QuoteService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole

router = APIRouter(prefix="/quotes", tags=["quotes"])

CustomerActor = Annotated[Actor, Depends(require_role(ActorRole.CUSTOMER))]
ReadActor = Annotated[
    Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.UNDERWRITER, ActorRole.ADMIN))
]
ServiceSession = Annotated[Session, Depends(get_service_session)]


@router.post("", status_code=201, summary="Create a quote")
def create_quote(
    body: QuoteRequest, actor: CustomerActor, session: ServiceSession
) -> QuoteResponse:
    """Contract 2.7 - priced on the active PUBLISHED rule version."""
    quote = QuoteService(session).create_quote(body.product, body.inputs, actor)
    return QuoteResponse.from_quote(quote)


@router.get("/{quote_id}", summary="Read a quote")
def get_quote(quote_id: str, actor: ReadActor, session: ServiceSession) -> QuoteDetailResponse:
    """Contract 2.8 - owner or staff; anything else is 404."""
    return QuoteDetailResponse.from_quote(QuoteService(session).get_quote(quote_id, actor))


@router.get("/{quote_id}/reprice", summary="Re-price a quote on its recorded version")
def reprice_quote(quote_id: str, actor: ReadActor, session: ServiceSession) -> RepriceResponse:
    """Contract 2.9 - recompute on the recorded rule version; never mutates the quote."""
    return RepriceResponse.from_result(QuoteService(session).reprice(quote_id, actor))
