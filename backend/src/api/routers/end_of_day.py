"""End-of-day trigger - endpoint 2.25 of `specs/design/api-contracts.md` (AC-07, AC-18, NFR-04).

ADMIN only; the same runner backs `python -m src.jobs.end_of_day` (DEC-011).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.renewals import EndOfDayRequest, EndOfDayResponse
from src.jobs.end_of_day import EndOfDayRunner
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole

router = APIRouter(prefix="/admin", tags=["admin"])

AdminActor = Annotated[Actor, Depends(require_role(ActorRole.ADMIN))]
ServiceSession = Annotated[Session, Depends(get_service_session)]


@router.post("/end-of-day", summary="Run the end-of-day renewal / lapse job")
def run_end_of_day(
    body: EndOfDayRequest, actor: AdminActor, session: ServiceSession
) -> EndOfDayResponse:
    """Contract 2.25 - idempotent per `as_of`; audited as RUN_END_OF_DAY with the admin's id."""
    return EndOfDayResponse.from_result(EndOfDayRunner(session).run(body.as_of, actor))
