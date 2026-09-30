"""Request and response schemas for the application endpoints (contract 2.10 and 2.11).

KYC arrives as a free mapping so the service validator can report every failing field with the
canonical detail codes; responses only ever carry the masked Aadhaar/PAN (NFR-03).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.api.schemas.quotes import timestamp
from src.service.application_service import (
    ApplicationView,
    DecisionView,
    OverrideView,
    ReasonView,
)


class ApplicationRequest(BaseModel):
    """``POST /api/applications`` body."""

    model_config = ConfigDict(extra="forbid")

    quote_id: str
    kyc: dict[str, Any]
    health_declaration: dict[str, Any] | None = None


class ReasonResponse(BaseModel):
    """A reason code and its description."""

    code: str
    description: str

    @classmethod
    def from_view(cls, view: ReasonView) -> ReasonResponse:
        """Build from a reason view."""
        return cls(code=view.code, description=view.description)


class DecisionResponse(BaseModel):
    """One underwriting decision."""

    decision_id: str
    decision: str
    reason_codes: list[str]
    reasons: list[ReasonResponse]
    rule_version: int
    decided_by: str
    comment: str | None
    created_at: str

    @classmethod
    def from_view(cls, view: DecisionView) -> DecisionResponse:
        """Build from a decision view."""
        return cls(
            decision_id=view.id,
            decision=view.decision,
            reason_codes=list(view.reason_codes),
            reasons=[ReasonResponse.from_view(r) for r in view.reasons],
            rule_version=view.rule_version,
            decided_by=view.decided_by,
            comment=view.comment,
            created_at=timestamp(view.created_at),
        )


class OverrideResponse(BaseModel):
    """One admin override."""

    override_id: str
    overridden_decision_id: str
    from_status: str
    to_status: str
    reason_code: str
    comment: str
    actor_id: str
    created_at: str

    @classmethod
    def from_view(cls, view: OverrideView) -> OverrideResponse:
        """Build from an override view."""
        return cls(
            override_id=view.id,
            overridden_decision_id=view.overridden_decision_id,
            from_status=view.from_status,
            to_status=view.to_status,
            reason_code=view.reason_code,
            comment=view.comment,
            actor_id=view.actor_id,
            created_at=timestamp(view.created_at),
        )


class MaskedKyc(BaseModel):
    """Applicant details with masked identifiers only."""

    full_name: str
    date_of_birth: str
    aadhaar_masked: str
    pan_masked: str
    address: str


class ApplicationResponse(BaseModel):
    """Application after synchronous underwriting."""

    application_id: str
    quote_id: str
    product: str
    rule_version: int
    status: str
    decision: str
    reason_codes: list[str]
    reasons: list[ReasonResponse]
    kyc: MaskedKyc
    status_history: list[str]
    created_at: str

    @classmethod
    def from_view(cls, view: ApplicationView) -> ApplicationResponse:
        """Build from an application view."""
        latest = view.latest
        return cls(
            application_id=view.id,
            quote_id=view.quote_id,
            product=view.product,
            rule_version=view.rule_version,
            status=view.status,
            decision=latest.decision,
            reason_codes=list(latest.reason_codes),
            reasons=[ReasonResponse.from_view(r) for r in latest.reasons],
            kyc=MaskedKyc(
                full_name=view.full_name,
                date_of_birth=view.date_of_birth.isoformat(),
                aadhaar_masked=view.aadhaar_masked,
                pan_masked=view.pan_masked,
                address=view.address,
            ),
            status_history=list(view.status_history),
            created_at=timestamp(view.created_at),
        )


class ApplicationDetailResponse(ApplicationResponse):
    """``GET /api/applications/{id}``: the summary plus decisions, overrides and policy number."""

    decisions: list[DecisionResponse]
    overrides: list[OverrideResponse]
    policy_number: str | None = None

    @classmethod
    def from_view(cls, view: ApplicationView) -> ApplicationDetailResponse:
        """Build from an application view."""
        summary = ApplicationResponse.from_view(view)
        return cls(
            **summary.model_dump(),
            decisions=[DecisionResponse.from_view(d) for d in view.decisions],
            overrides=[OverrideResponse.from_view(o) for o in view.overrides],
        )
