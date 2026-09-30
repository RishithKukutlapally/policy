"""Application router - endpoints 2.10 and 2.11 of `specs/design/api-contracts.md` (AC-03, AC-04).

POST is CUSTOMER only (the service answers 404 for a quote the caller does not own); GET is open
to the owner, UNDERWRITER and ADMIN.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.applications import (
    ApplicationDetailResponse,
    ApplicationRequest,
    ApplicationResponse,
)
from src.service.application_service import ApplicationService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole

router = APIRouter(prefix="/applications", tags=["applications"])

CustomerActor = Annotated[Actor, Depends(require_role(ActorRole.CUSTOMER))]
ReadActor = Annotated[
    Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.UNDERWRITER, ActorRole.ADMIN))
]
ServiceSession = Annotated[Session, Depends(get_service_session)]


@router.post("", status_code=201, summary="Submit an application")
def submit_application(
    body: ApplicationRequest, actor: CustomerActor, session: ServiceSession
) -> ApplicationResponse:
    """Contract 2.10 - validate, decide synchronously and persist."""
    view = ApplicationService(session).submit(
        body.quote_id, body.kyc, body.health_declaration, actor
    )
    return ApplicationResponse.from_view(view)


@router.get("/{application_id}", summary="Read an application")
def get_application(
    application_id: str, actor: ReadActor, session: ServiceSession
) -> ApplicationDetailResponse:
    """Contract 2.11 - owner or staff; anything else is 404."""
    view = ApplicationService(session).get(application_id, actor)
    return ApplicationDetailResponse.from_view(view)
