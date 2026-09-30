"""Cancellation router - endpoints 2.23 and 2.24 of `specs/design/api-contracts.md` (AC-08, AC-19).

Open to the owning CUSTOMER and ADMIN; the services answer 404 for another customer's policy.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.cancellations import CancelRequest, CancelResponse, RefundBreakdownResponse
from src.service.cancellation_service import CancellationService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole

router = APIRouter(prefix="/policies", tags=["cancellations"])

CancellingActor = Annotated[Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.ADMIN))]
ServiceSession = Annotated[Session, Depends(get_service_session)]


@router.get("/{policy_number}/cancellation-preview", summary="Preview the cancellation refund")
def cancellation_preview(
    policy_number: str, actor: CancellingActor, session: ServiceSession, date: dt.date
) -> RefundBreakdownResponse:
    """Contract 2.23 - refund type, gross pro-rata, admin fee and net; persists nothing."""
    view = CancellationService(session).preview(policy_number, date, actor)
    return RefundBreakdownResponse.from_view(view)


@router.post("/{policy_number}/cancel", summary="Cancel a policy")
def cancel_policy(
    policy_number: str, body: CancelRequest, actor: CancellingActor, session: ServiceSession
) -> CancelResponse:
    """Contract 2.24 - appends the refund and moves the policy to CANCELLED."""
    result = CancellationService(session).cancel(
        policy_number, body.cancellation_date, body.reason, actor
    )
    return CancelResponse.from_result(result)
