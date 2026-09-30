"""Underwriter workbench: queue, decisions, admin override, audit trail (AC-14, AC-09).

Every action appends rows (decision, override, audit) and moves the application status in one
transaction; earlier decision rows are never touched (NFR-02). Audit rows carry the acting
user's id (NFR-04). Role checks are repeated here as defence in depth; the API layer is the
primary gate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Final

from sqlalchemy.orm import Session

from src.repository.models import Application, AuditAction, AuditEntityType, AuditRecord
from src.repository.quote_repository import QuoteRepository
from src.service.application_service import (
    ApplicationReader,
    ApplicationView,
    DecisionView,
    OverrideView,
    decision_view,
    override_view,
)
from src.service.audit_service import AuditService
from src.service.quote_service import ActingActor
from src.types.enums import ActorRole, ApplicationStatus, Decision, UnderwriterDecision
from src.types.errors import (
    ForbiddenError,
    InvalidApplicationStateError,
    NotFoundError,
    ValidationError,
)
from src.types.rules import RuleSet

_COMMENT_MAX: Final = 500
_OVERRIDE_COMMENT_MIN: Final = 10
_QUEUE_STATUSES: Final = (ApplicationStatus.MANUAL_REVIEW, ApplicationStatus.DECLINED)


@dataclass(frozen=True, slots=True)
class QueueItem:
    """One case in the underwriter / admin queue (masked applicant only)."""

    application_id: str
    product: str
    status: str
    rule_version: int
    reason_codes: tuple[str, ...]
    full_name: str
    aadhaar_masked: str
    pan_masked: str
    sum_insured: Decimal
    premium: Decimal
    submitted_at: datetime
    decisions: tuple[DecisionView, ...]


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Outcome of an underwriter decision."""

    application_id: str
    status: str
    decision: DecisionView


@dataclass(frozen=True, slots=True)
class OverrideResult:
    """Outcome of an admin override."""

    application_id: str
    status: str
    override: OverrideView


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Read model of one audit row."""

    action: str
    actor_id: str
    actor_role: str
    entity_type: str
    entity_id: str
    detail: dict[str, Any] | None
    correlation_id: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditTrail:
    """Decisions, overrides and audit rows of one application, oldest first."""

    application_id: str
    decisions: tuple[DecisionView, ...]
    overrides: tuple[OverrideView, ...]
    audit_records: tuple[AuditEntry, ...]


def _audit_entry(row: AuditRecord) -> AuditEntry:
    return AuditEntry(
        action=row.action,
        actor_id=row.actor_id,
        actor_role=row.actor_role,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        detail=dict(row.detail) if row.detail else None,
        correlation_id=row.correlation_id,
        created_at=row.created_at,
    )


def _invalid(field: str, code: str) -> ValidationError:
    return ValidationError("Request validation failed", [{"field": field, "code": code}])


def _require_role(actor: ActingActor, *roles: ActorRole) -> None:
    if actor.role not in roles:
        raise ForbiddenError(f"Role {actor.role.value} is not allowed to do this")


def _check_codes(rule_set: RuleSet, codes: Sequence[str], field: str) -> None:
    known = rule_set.underwriting.reason_codes
    if any(code not in known for code in codes):
        raise _invalid(field, "UNKNOWN_REASON_CODE")


class UnderwritingService(ApplicationReader):
    """Queue, approve/decline, override and audit trail for underwriting cases."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._quotes = QuoteRepository(session)
        self._audit = AuditService(session)

    def queue(self, status: str | None, actor: ActingActor) -> list[QueueItem]:
        """MANUAL_REVIEW cases for an UNDERWRITER; MANUAL_REVIEW and/or DECLINED for an ADMIN."""
        _require_role(actor, ActorRole.UNDERWRITER, ActorRole.ADMIN)
        wanted = self._queue_statuses(status, actor)
        rows = self._applications.list_by_statuses(wanted)
        return [self._queue_item(row) for row in rows]

    def decide(
        self,
        application_id: str,
        decision: str,
        reason_codes: Sequence[str],
        comment: str | None,
        actor: ActingActor,
    ) -> DecisionResult:
        """Approve (AUTO_BIND) or decline (DECLINED) a MANUAL_REVIEW case."""
        _require_role(actor, ActorRole.UNDERWRITER)
        choice = self._parse_choice(decision)
        if not reason_codes:
            raise _invalid("reason_codes", "REQUIRED")
        if comment is not None and len(comment) > _COMMENT_MAX:
            raise _invalid("comment", "OUT_OF_RANGE")
        row = self._case(application_id)
        if row.status != ApplicationStatus.MANUAL_REVIEW.value:
            raise InvalidApplicationStateError("Application is not in MANUAL_REVIEW")
        rule_set = self.rule_set_for(row.product, row.rule_version)
        _check_codes(rule_set, reason_codes, "reason_codes")
        approve = choice is UnderwriterDecision.APPROVE
        stored = Decision.AUTO_BIND if approve else Decision.DECLINE
        target = ApplicationStatus.AUTO_BIND if approve else ApplicationStatus.DECLINED
        action = AuditAction.UW_APPROVE if approve else AuditAction.UW_DECLINE
        new = self._decisions.add(
            application_id=row.id,
            decision=stored,
            reason_codes=list(reason_codes),
            product=row.product,
            rule_version=row.rule_version,
            decided_by=actor.actor_id,
            comment=comment,
        )
        self._applications.transition(row, target)
        detail: dict[str, Any] = {"reason_codes": sorted(reason_codes), "comment": comment}
        self._record(action, row.id, actor, detail)
        self._session.commit()
        return DecisionResult(row.id, row.status, decision_view(new, rule_set))

    def override(
        self, application_id: str, reason_code: str, comment: str, actor: ActingActor
    ) -> OverrideResult:
        """Override a DECLINED application to AUTO_BIND (ADMIN only)."""
        _require_role(actor, ActorRole.ADMIN)
        if not _OVERRIDE_COMMENT_MIN <= len(comment) <= _COMMENT_MAX:
            raise _invalid("comment", "OUT_OF_RANGE")
        row = self._case(application_id)
        if row.status != ApplicationStatus.DECLINED.value:
            raise InvalidApplicationStateError("Application is not DECLINED")
        rule_set = self.rule_set_for(row.product, row.rule_version)
        _check_codes(rule_set, [reason_code], "reason_code")
        original = self._decisions.latest_for_application(row.id)
        if original is None:
            raise NotFoundError("Application has no decision to override")
        self._decisions.add(
            application_id=row.id,
            decision=Decision.AUTO_BIND,
            reason_codes=[reason_code],
            product=row.product,
            rule_version=row.rule_version,
            decided_by=actor.actor_id,
            comment=comment,
        )
        record = self._overrides.add(
            application_id=row.id,
            original_decision_id=original.id,
            reason_code=reason_code,
            comment=comment,
            actor_id=actor.actor_id,
        )
        self._applications.transition(row, ApplicationStatus.AUTO_BIND)
        detail: dict[str, Any] = {"reason_code": reason_code, "comment": comment}
        self._record(AuditAction.UW_OVERRIDE_DECLINE, row.id, actor, detail)
        self._session.commit()
        return OverrideResult(row.id, row.status, override_view(record))

    def audit_trail(self, application_id: str, actor: ActingActor) -> AuditTrail:
        """Decisions, overrides and audit rows of one application."""
        _require_role(actor, ActorRole.UNDERWRITER, ActorRole.ADMIN)
        row = self._case(application_id)
        view: ApplicationView = self.view(row)
        records = self._audit.list_for_entity(AuditEntityType.APPLICATION, row.id)
        return AuditTrail(
            application_id=row.id,
            decisions=view.decisions,
            overrides=view.overrides,
            audit_records=tuple(_audit_entry(r) for r in records),
        )

    def _case(self, application_id: str) -> Application:
        row = self._applications.get(application_id)
        if row is None:
            raise NotFoundError("Application not found")
        return row

    def _record(
        self, action: AuditAction, application_id: str, actor: ActingActor, detail: dict[str, Any]
    ) -> None:
        self._audit.record(
            action=action,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type=AuditEntityType.APPLICATION,
            entity_id=application_id,
            detail=detail,
        )

    @staticmethod
    def _parse_choice(decision: str) -> UnderwriterDecision:
        try:
            return UnderwriterDecision(decision)
        except ValueError:
            raise _invalid("decision", "UNKNOWN_CODE") from None

    @staticmethod
    def _queue_statuses(status: str | None, actor: ActingActor) -> list[ApplicationStatus]:
        if status is None:
            if actor.role is ActorRole.ADMIN:
                return list(_QUEUE_STATUSES)
            return [ApplicationStatus.MANUAL_REVIEW]
        try:
            chosen = ApplicationStatus(status)
        except ValueError:
            raise _invalid("status", "UNKNOWN_CODE") from None
        if chosen not in _QUEUE_STATUSES:
            raise _invalid("status", "UNKNOWN_CODE")
        if actor.role is ActorRole.UNDERWRITER and chosen is not ApplicationStatus.MANUAL_REVIEW:
            raise ForbiddenError("Role UNDERWRITER may only list MANUAL_REVIEW cases")
        return [chosen]

    def _queue_item(self, row: Application) -> QueueItem:
        view = self.view(row)
        quote = self._quotes.get(row.quote_id)
        if quote is None:
            raise NotFoundError("Quote not found")
        return QueueItem(
            application_id=row.id,
            product=row.product,
            status=row.status,
            rule_version=row.rule_version,
            reason_codes=view.latest.reason_codes,
            full_name=row.full_name,
            aadhaar_masked=row.aadhaar_masked,
            pan_masked=row.pan_masked,
            sum_insured=quote.sum_insured,
            premium=quote.premium,
            submitted_at=row.created_at,
            decisions=view.decisions,
        )
