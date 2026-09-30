"""Application capture and automatic underwriting (AC-03, AC-04).

``submit`` loads the caller's quote, rejects a stale one, validates KYC stub + risk inputs, runs the
decision engine and persists the application with its first SYSTEM decision in one transaction.
Only masked Aadhaar/PAN are stored and none of them is ever logged (NFR-03). Services hand view
objects to the API layer, never ORM rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

from sqlalchemy.orm import Session

from src.config.rule_loader import build_rule_set
from src.domain.application_validator import FieldError, validate_application
from src.domain.underwriting_rules import decide
from src.lib.logging import mask_pii
from src.repository.application_repository import ApplicationRepository
from src.repository.models import (
    Application,
    RuleSetVersion,
    UnderwritingDecision,
    UnderwritingOverride,
)
from src.repository.quote_repository import QuoteRepository
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.repository.underwriting_repository import (
    UnderwritingDecisionRepository,
    UnderwritingOverrideRepository,
)
from src.service.quote_service import ActingActor
from src.types.enums import ActorRole, ApplicationStatus, Decision, ProductCode, RuleSetStatus
from src.types.errors import (
    NoPublishedVersionError,
    NotFoundError,
    QuoteStaleError,
    ValidationError,
)
from src.types.rules import RuleSet

SYSTEM_ACTOR: Final = "SYSTEM"
_STATUS_FOR: Final[Mapping[Decision, ApplicationStatus]] = {
    Decision.AUTO_BIND: ApplicationStatus.AUTO_BIND,
    Decision.MANUAL_REVIEW: ApplicationStatus.MANUAL_REVIEW,
    Decision.DECLINE: ApplicationStatus.DECLINED,
}


@dataclass(frozen=True, slots=True)
class ReasonView:
    """A reason code with its description from the rule version."""

    code: str
    description: str


@dataclass(frozen=True, slots=True)
class DecisionView:
    """Read model of one underwriting decision."""

    id: str
    decision: str
    reason_codes: tuple[str, ...]
    reasons: tuple[ReasonView, ...]
    rule_version: int
    decided_by: str
    comment: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OverrideView:
    """Read model of one admin override."""

    id: str
    overridden_decision_id: str
    from_status: str
    to_status: str
    reason_code: str
    comment: str
    actor_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ApplicationView:
    """Read model of an application: masked KYC, latest decision, history."""

    id: str
    quote_id: str
    product: str
    rule_version: int
    status: str
    customer_id: str
    full_name: str
    date_of_birth: date
    address: str
    aadhaar_masked: str
    pan_masked: str
    status_history: tuple[str, ...]
    created_at: datetime
    decisions: tuple[DecisionView, ...]
    overrides: tuple[OverrideView, ...]

    @property
    def latest(self) -> DecisionView:
        """The current (latest) decision."""
        return self.decisions[-1]


def reasons_for(rule_set: RuleSet, codes: Sequence[str]) -> tuple[ReasonView, ...]:
    """Descriptions of ``codes`` taken from the rule version's dictionary."""
    known = rule_set.underwriting.reason_codes
    return tuple(ReasonView(code, known.get(code, "")) for code in codes)


def decision_view(row: UnderwritingDecision, rule_set: RuleSet) -> DecisionView:
    """Copy a stored decision into a view."""
    return DecisionView(
        id=row.id,
        decision=row.decision,
        reason_codes=tuple(row.reason_codes),
        reasons=reasons_for(rule_set, row.reason_codes),
        rule_version=row.rule_version,
        decided_by=row.decided_by,
        comment=row.comment,
        created_at=row.created_at,
    )


def override_view(row: UnderwritingOverride) -> OverrideView:
    """Copy a stored override into a view."""
    return OverrideView(
        id=row.id,
        overridden_decision_id=row.original_decision_id,
        from_status=row.from_status,
        to_status=row.to_status,
        reason_code=row.reason_code,
        comment=row.comment,
        actor_id=row.actor_id,
        created_at=row.created_at,
    )


class ApplicationReader:
    """Shared read side: rule-set lookup and view assembly for applications."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._applications = ApplicationRepository(session)
        self._decisions = UnderwritingDecisionRepository(session)
        self._overrides = UnderwritingOverrideRepository(session)
        self._versions = RuleSetVersionRepository(session)

    def rule_set_for(self, product: str, version: int) -> RuleSet:
        """Latest PUBLISHED rule set of the recorded ``(product, version)``."""
        rows = [
            r
            for r in self._versions.list_for_product(ProductCode(product))
            if r.version == version and r.status == RuleSetStatus.PUBLISHED.value
        ]
        if not rows:
            raise NoPublishedVersionError(f"Recorded rule version {version} is unavailable")
        return _rule_set(max(rows, key=lambda r: r.revision))

    def view(self, row: Application) -> ApplicationView:
        """Assemble the full view of ``row`` with decisions and overrides."""
        rule_set = self.rule_set_for(row.product, row.rule_version)
        decisions = tuple(
            decision_view(d, rule_set) for d in self._decisions.list_for_application(row.id)
        )
        overrides = tuple(override_view(o) for o in self._overrides.list_for_application(row.id))
        return ApplicationView(
            id=row.id,
            quote_id=row.quote_id,
            product=row.product,
            rule_version=row.rule_version,
            status=row.status,
            customer_id=row.customer_id,
            full_name=row.full_name,
            date_of_birth=row.date_of_birth,
            address=row.address,
            aadhaar_masked=row.aadhaar_masked,
            pan_masked=row.pan_masked,
            status_history=tuple(row.status_history),
            created_at=row.created_at,
            decisions=decisions,
            overrides=overrides,
        )


def _rule_set(row: RuleSetVersion) -> RuleSet:
    return build_rule_set(row.content, label=f"{row.product} v{row.version}")


class ApplicationService(ApplicationReader):
    """Creates applications from quotes and reads them back (owner-scoped for customers)."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._quotes = QuoteRepository(session)

    def submit(
        self,
        quote_id: str,
        kyc: Mapping[str, Any],
        health_declaration: Mapping[str, Any] | None,
        actor: ActingActor,
    ) -> ApplicationView:
        """Validate, decide and persist the application and its first decision (one commit)."""
        quote = self._quotes.get(quote_id)
        if quote is None or quote.actor_id != actor.actor_id:
            raise NotFoundError("Quote not found")
        product = ProductCode(quote.product)
        active = self._versions.active_for_product(product)
        if active is None or active.version != quote.rule_version:
            raise QuoteStaleError("The quote's rule version is no longer active")
        rule_set = _rule_set(active)
        errors = _field_errors(rule_set, kyc, quote.inputs, health_declaration)
        if errors:
            raise ValidationError(
                "Application failed validation",
                [{"field": e.field, "code": e.code} for e in errors],
            )
        outcome = decide(rule_set, _decision_inputs(product, quote.inputs, health_declaration))
        status = _STATUS_FOR[outcome.decision]
        row = self._applications.add(
            quote_id=quote.id,
            customer_id=actor.actor_id,
            product=quote.product,
            rule_version=quote.rule_version,
            status=status,
            status_history=[
                ApplicationStatus.SUBMITTED.value,
                ApplicationStatus.UNDERWRITING.value,
                status.value,
            ],
            full_name=str(kyc["full_name"]).strip(),
            date_of_birth=date.fromisoformat(str(kyc["date_of_birth"])),
            address=str(kyc["address"]).strip(),
            aadhaar_masked=mask_pii(kyc["aadhaar"], "aadhaar"),
            pan_masked=mask_pii(kyc["pan"], "pan"),
            risk_inputs=dict(quote.inputs),
        )
        self._decisions.add(
            application_id=row.id,
            decision=outcome.decision,
            reason_codes=list(outcome.reason_codes),
            product=quote.product,
            rule_version=outcome.rule_version,
            decided_by=SYSTEM_ACTOR,
            comment=None,
        )
        self._session.commit()
        return self.view(row)

    def get(self, application_id: str, actor: ActingActor) -> ApplicationView:
        """The application, or 404 when unknown or another customer's."""
        row = self._applications.get(application_id)
        if row is None or (actor.role is ActorRole.CUSTOMER and row.customer_id != actor.actor_id):
            raise NotFoundError("Application not found")
        return self.view(row)


def _field_errors(
    rule_set: RuleSet,
    kyc: Mapping[str, Any],
    risk: Mapping[str, Any],
    health: Mapping[str, Any] | None,
) -> list[FieldError]:
    errors = validate_application(rule_set, kyc, risk, health)
    if rule_set.product is not ProductCode.TERM_LIFE and health is not None:
        errors.append(FieldError("health_declaration", "UNKNOWN_FIELD"))
    return errors


def _decision_inputs(
    product: ProductCode, risk: Mapping[str, Any], health: Mapping[str, Any] | None
) -> dict[str, Any]:
    inputs = dict(risk)
    if product is ProductCode.TERM_LIFE and health is not None:
        inputs["has_pre_existing_condition"] = health.get("has_pre_existing_condition") is True
    return inputs
