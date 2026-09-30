"""Policy router - endpoints 2.16 to 2.18 of `specs/design/api-contracts.md` (AC-05, AC-15).

Issuance is open to the owning CUSTOMER and ADMIN; reads are open to the owner, UNDERWRITER and
ADMIN (owner scoping lives in the services, which answer 404 for another customer's policy).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.policies import PolicyDetailResponse, PolicySummaryResponse
from src.service.policy_query_service import PolicyQueryService
from src.service.policy_service import PolicyService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole, PolicyStatus, ProductCode
from src.types.errors import ValidationError

router = APIRouter(tags=["policies"])

IssuingActor = Annotated[Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.ADMIN))]
ReadActor = Annotated[
    Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.UNDERWRITER, ActorRole.ADMIN))
]
ServiceSession = Annotated[Session, Depends(get_service_session)]


def _filter[EnumT: StrEnum](enum: type[EnumT], raw: str | None, field: str) -> EnumT | None:
    """Parse an optional query filter, or raise 422 ``UNKNOWN_CODE``."""
    if raw is None:
        return None
    try:
        return enum(raw)
    except ValueError:
        raise ValidationError(
            f"Unknown {field} filter", [{"field": field, "code": "UNKNOWN_CODE"}]
        ) from None


@router.post(
    "/applications/{application_id}/issue", status_code=201, summary="Issue a bound application"
)
def issue_policy(
    application_id: str, actor: IssuingActor, session: ServiceSession
) -> PolicySummaryResponse:
    """Contract 2.16 - one transaction: policy, transition, first-term payment, application."""
    view = PolicyService(session).issue(application_id, actor)
    return PolicySummaryResponse.from_view(view)


@router.get("/policies", summary="List policies")
def list_policies(
    actor: ReadActor,
    session: ServiceSession,
    product: str | None = None,
    status: str | None = None,
) -> list[PolicySummaryResponse]:
    """Contract 2.17 - a CUSTOMER sees only their own policies."""
    views = PolicyQueryService(session).list_policies(
        actor,
        product=_filter(ProductCode, product, "product"),
        status=_filter(PolicyStatus, status, "status"),
    )
    return [PolicySummaryResponse.from_view(view) for view in views]


@router.get("/policies/{policy_number}", summary="Read a policy")
def get_policy(
    policy_number: str, actor: ReadActor, session: ServiceSession
) -> PolicyDetailResponse:
    """Contract 2.18 - the policy with its endorsements, transitions, payments and refunds."""
    view = PolicyQueryService(session).get_policy(policy_number, actor)
    return PolicyDetailResponse.from_detail(view)
