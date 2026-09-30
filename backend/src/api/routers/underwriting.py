"""Underwriting router - endpoints 2.12 to 2.15 of `specs/design/api-contracts.md`.

Roles are enforced here with ``require_role`` (NFR-04): the queue is UNDERWRITER/ADMIN, decisions
are UNDERWRITER, overrides are ADMIN only, and the audit trail is UNDERWRITER/ADMIN. The router
maps HTTP to one service call; typed errors become the canonical envelope in `src.api.errors`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.underwriting import (
    AuditTrailResponse,
    DecisionRequest,
    DecisionResultResponse,
    OverrideRequest,
    OverrideResultResponse,
    QueueItemResponse,
)
from src.service.underwriting_service import UnderwritingService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole

router = APIRouter(prefix="/underwriting", tags=["underwriting"])

StaffActor = Annotated[Actor, Depends(require_role(ActorRole.UNDERWRITER, ActorRole.ADMIN))]
UnderwriterActor = Annotated[Actor, Depends(require_role(ActorRole.UNDERWRITER))]
AdminActor = Annotated[Actor, Depends(require_role(ActorRole.ADMIN))]
ServiceSession = Annotated[Session, Depends(get_service_session)]


@router.get("/queue", summary="Underwriting queue, oldest first")
def get_queue(
    actor: StaffActor, session: ServiceSession, status: Annotated[str | None, Query()] = None
) -> list[QueueItemResponse]:
    """Contract 2.12 - UNDERWRITER sees MANUAL_REVIEW; ADMIN sees MANUAL_REVIEW and DECLINED."""
    items = UnderwritingService(session).queue(status, actor)
    return [QueueItemResponse.from_item(item) for item in items]


@router.post("/applications/{application_id}/decision", summary="Approve or decline a case")
def decide_application(
    application_id: str, body: DecisionRequest, actor: UnderwriterActor, session: ServiceSession
) -> DecisionResultResponse:
    """Contract 2.13 - append a decision and an audit row."""
    result = UnderwritingService(session).decide(
        application_id, body.decision, body.reason_codes, body.comment, actor
    )
    return DecisionResultResponse.from_result(result)


@router.post("/applications/{application_id}/override", summary="Override a DECLINE")
def override_application(
    application_id: str, body: OverrideRequest, actor: AdminActor, session: ServiceSession
) -> OverrideResultResponse:
    """Contract 2.14 - DECLINED to AUTO_BIND with an override row and an audit row."""
    result = UnderwritingService(session).override(
        application_id, body.reason_code, body.comment, actor
    )
    return OverrideResultResponse.from_result(result)


@router.get("/applications/{application_id}/audit", summary="Decisions, overrides and audit rows")
def get_audit_trail(
    application_id: str, actor: StaffActor, session: ServiceSession
) -> AuditTrailResponse:
    """Contract 2.15 - all lists oldest first."""
    trail = UnderwritingService(session).audit_trail(application_id, actor)
    return AuditTrailResponse.from_trail(trail)
