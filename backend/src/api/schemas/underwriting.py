"""Request and response schemas for the underwriting endpoints (contract 2.12 to 2.15).

Bodies stay loose (plain strings and lists) so the service reports the canonical detail codes
(`REQUIRED`, `OUT_OF_RANGE`, `UNKNOWN_CODE`, `UNKNOWN_REASON_CODE`). Money is a string (NFR-01).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.api.schemas.applications import DecisionResponse, OverrideResponse
from src.api.schemas.quotes import money, timestamp
from src.service.underwriting_service import (
    AuditEntry,
    AuditTrail,
    DecisionResult,
    OverrideResult,
    QueueItem,
)


class DecisionRequest(BaseModel):
    """``POST .../decision`` body."""

    model_config = ConfigDict(extra="forbid")

    decision: str
    reason_codes: list[str] = []
    comment: str | None = None


class OverrideRequest(BaseModel):
    """``POST .../override`` body."""

    model_config = ConfigDict(extra="forbid")

    reason_code: str
    comment: str


class Applicant(BaseModel):
    """Masked applicant shown in the queue."""

    full_name: str
    aadhaar_masked: str
    pan_masked: str


class QueueItemResponse(BaseModel):
    """One queue case with its decision history."""

    application_id: str
    product: str
    status: str
    rule_version: int
    reason_codes: list[str]
    applicant: Applicant
    sum_insured: str
    premium: str
    submitted_at: str
    decisions: list[DecisionResponse]

    @classmethod
    def from_item(cls, item: QueueItem) -> QueueItemResponse:
        """Build from a queue item."""
        return cls(
            application_id=item.application_id,
            product=item.product,
            status=item.status,
            rule_version=item.rule_version,
            reason_codes=list(item.reason_codes),
            applicant=Applicant(
                full_name=item.full_name,
                aadhaar_masked=item.aadhaar_masked,
                pan_masked=item.pan_masked,
            ),
            sum_insured=money(item.sum_insured),
            premium=money(item.premium),
            submitted_at=timestamp(item.submitted_at),
            decisions=[DecisionResponse.from_view(d) for d in item.decisions],
        )


class DecisionResultResponse(BaseModel):
    """Result of an underwriter decision."""

    application_id: str
    status: str
    decision: DecisionResponse

    @classmethod
    def from_result(cls, result: DecisionResult) -> DecisionResultResponse:
        """Build from a decision result."""
        return cls(
            application_id=result.application_id,
            status=result.status,
            decision=DecisionResponse.from_view(result.decision),
        )


class OverrideResultResponse(BaseModel):
    """Result of an admin override."""

    application_id: str
    status: str
    override: OverrideResponse

    @classmethod
    def from_result(cls, result: OverrideResult) -> OverrideResultResponse:
        """Build from an override result."""
        return cls(
            application_id=result.application_id,
            status=result.status,
            override=OverrideResponse.from_view(result.override),
        )


class AuditEntryResponse(BaseModel):
    """One audit row."""

    action: str
    actor_id: str
    actor_role: str
    entity_type: str
    entity_id: str
    detail: dict[str, Any] | None
    correlation_id: str | None
    created_at: str

    @classmethod
    def from_entry(cls, entry: AuditEntry) -> AuditEntryResponse:
        """Build from an audit entry."""
        return cls(
            action=entry.action,
            actor_id=entry.actor_id,
            actor_role=entry.actor_role,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            detail=entry.detail,
            correlation_id=entry.correlation_id,
            created_at=timestamp(entry.created_at),
        )


class AuditTrailResponse(BaseModel):
    """``GET .../audit`` response."""

    application_id: str
    decisions: list[DecisionResponse]
    overrides: list[OverrideResponse]
    audit_records: list[AuditEntryResponse]

    @classmethod
    def from_trail(cls, trail: AuditTrail) -> AuditTrailResponse:
        """Build from an audit trail."""
        return cls(
            application_id=trail.application_id,
            decisions=[DecisionResponse.from_view(d) for d in trail.decisions],
            overrides=[OverrideResponse.from_view(o) for o in trail.overrides],
            audit_records=[AuditEntryResponse.from_entry(a) for a in trail.audit_records],
        )
