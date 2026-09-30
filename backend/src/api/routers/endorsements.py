"""Endorsement router - endpoint 2.19 of `specs/design/api-contracts.md` (AC-06, AC-16, AC-10).

One endpoint: ``?preview=true`` answers 200 and persists nothing; the real call answers 201. Open
to the owning CUSTOMER and ADMIN (ownership is enforced in the service: 404 for someone else's).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.endorsements import EndorsementRequest, EndorsementResponse
from src.service.endorsement_service import EndorsementService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole, EndorsementType
from src.types.errors import ValidationError

router = APIRouter(tags=["endorsements"])

EndorsingActor = Annotated[Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.ADMIN))]
ServiceSession = Annotated[Session, Depends(get_service_session)]


def _kind(raw: str) -> EndorsementType:
    try:
        return EndorsementType(raw)
    except ValueError:
        raise ValidationError(
            "Unknown endorsement type", [{"field": "type", "code": "UNKNOWN_CODE"}]
        ) from None


@router.post(
    "/policies/{policy_number}/endorsements",
    status_code=201,
    summary="Endorse a policy (or preview the endorsement)",
)
def endorse_policy(
    policy_number: str,
    body: EndorsementRequest,
    actor: EndorsingActor,
    session: ServiceSession,
    response: Response,
    preview: bool = False,
) -> EndorsementResponse:
    """Contract 2.19 - atomic endorsement, or a side-effect-free preview with 200."""
    service = EndorsementService(session)
    kind = _kind(body.type)
    if preview:
        response.status_code = 200
        return EndorsementResponse.from_view(
            service.preview(policy_number, kind, body.changes(), actor)
        )
    return EndorsementResponse.from_view(service.apply(policy_number, kind, body.changes(), actor))
