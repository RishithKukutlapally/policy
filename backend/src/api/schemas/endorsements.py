"""Request/response schemas for ``POST /api/policies/{policy_number}/endorsements`` (contract 2.19).

Money leaves as two-decimal strings (NFR-01). Field-level shape rules (blank, range, enum) are
enforced by the endorsement service so that every finding is reported at once.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.api.schemas.policies import PolicySummaryResponse
from src.api.schemas.quotes import money, timestamp
from src.service.endorsement_service import EndorsementResultView


class EndorsementRequest(BaseModel):
    """Body discriminated by ``type``; unrelated fields are simply left out."""

    model_config = ConfigDict(extra="forbid")

    type: str
    address: str | None = None
    nominee_name: str | None = None
    relationship: str | None = None
    share_percent: Any = None
    # Deliberately loose on the wire so a JSON number reaches the service and is refused there
    # as 422 MONEY_MUST_BE_STRING (contract 0.4) rather than as a generic schema error.
    new_sum_insured: str | int | float | None = None

    def changes(self) -> dict[str, Any]:
        """The supplied endorsement fields, without ``type`` and unset values."""
        return self.model_dump(exclude={"type"}, exclude_none=True)


class EndorsementResponse(BaseModel):
    """A created endorsement (201) or its preview (200)."""

    policy_number: str
    type: str
    preview: bool
    before: dict[str, Any]
    after: dict[str, Any]
    new_premium: str
    premium_delta: str
    rule_version: int
    endorsement_date: str
    endorsement_id: str | None = None
    created_at: str | None = None
    policy: PolicySummaryResponse | None = None

    @classmethod
    def from_view(cls, view: EndorsementResultView) -> EndorsementResponse:
        """Build from an endorsement result view."""
        return cls(
            policy_number=view.policy_number,
            type=view.endorsement_type,
            preview=view.preview,
            before=view.before,
            after=view.after,
            new_premium=money(view.new_premium),
            premium_delta=money(view.premium_delta),
            rule_version=view.rule_version,
            endorsement_date=view.endorsement_date.isoformat(),
            endorsement_id=view.endorsement_id,
            created_at=None if view.created_at is None else timestamp(view.created_at),
            policy=None if view.policy is None else PolicySummaryResponse.from_view(view.policy),
        )
