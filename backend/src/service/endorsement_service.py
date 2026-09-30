"""Mid-term endorsements: preview and atomic apply (AC-06, AC-16, AC-10; NFR-01, NFR-02).

:meth:`EndorsementService.apply` validates the request on the policy's *own* rule version, then in
ONE transaction appends the immutable ``Endorsement`` row, moves the ``Policy`` projection, appends
the ``-> ENDORSED`` transition and (for ADMIN actors) the ``ENDORSEMENT_CREATED`` audit row. It
commits once; any failure rolls the whole unit back. :meth:`EndorsementService.preview` computes the
same outcome and writes nothing. Nominee names and addresses are PII-adjacent and are never logged.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy.orm import Session

from src.domain.endorsement_rules import Finding, build_outcome, validate_endorsement
from src.domain.money import to_money
from src.domain.policy_state_machine import assert_transition
from src.domain.premium_calculator import calculate_premium
from src.domain.term_days import term_days, unused_days
from src.lib.clock import today
from src.repository.models import AuditAction, AuditEntityType, Policy
from src.repository.policy_lifecycle_repository import PolicyLifecycleRepository
from src.repository.policy_repository import PolicyRepository
from src.service.application_service import ApplicationReader
from src.service.audit_service import AuditService
from src.service.ownership import owned_policy
from src.service.policy_service import PolicySummaryView, summary_view
from src.service.quote_service import ActingActor
from src.types.enums import ActorRole, EndorsementType, PolicyStatus
from src.types.errors import ValidationError

_RELATIONSHIPS: Final = frozenset({"SPOUSE", "CHILD", "PARENT", "SIBLING", "OTHER"})
_MAX_ADDRESS: Final = 300
_ENDORSED_REASON: Final = "ENDORSEMENT:"


@dataclass(frozen=True, slots=True)
class EndorsementResultView:
    """Outcome of a preview (``endorsement_id is None``) or of an applied endorsement."""

    policy_number: str
    endorsement_type: str
    preview: bool
    before: dict[str, Any]
    after: dict[str, Any]
    new_premium: Decimal
    premium_delta: Decimal
    rule_version: int
    endorsement_date: date
    endorsement_id: str | None = None
    created_at: datetime | None = None
    policy: PolicySummaryView | None = None


@dataclass(frozen=True, slots=True)
class _Plan:
    """A validated endorsement, ready to be previewed or persisted."""

    before: dict[str, Any]
    after: dict[str, Any]
    attributes: dict[str, Any]
    new_premium: Decimal
    premium_delta: Decimal
    rule_version: int
    endorsement_date: date


def _decimal_field(changes: Mapping[str, Any], name: str) -> tuple[Decimal | None, list[Finding]]:
    raw = changes.get(name)
    if not isinstance(raw, str):
        return None, [(name, "MONEY_MUST_BE_STRING" if raw is not None else "REQUIRED")]
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None, [(name, "INVALID_FORMAT")]
    return (value, []) if value.is_finite() else (None, [(name, "INVALID_FORMAT")])


def _address_findings(policy: Policy, changes: Mapping[str, Any]) -> list[Finding]:
    address = changes.get("address")
    if not isinstance(address, str) or not address.strip():
        return [("address", "REQUIRED")]
    if len(address) > _MAX_ADDRESS:
        return [("address", "INVALID_FORMAT")]
    return [("address", "UNCHANGED")] if address == policy.address else []


def _nominee_findings(_policy: Policy, changes: Mapping[str, Any]) -> list[Finding]:
    found: list[Finding] = []
    if changes.get("relationship") not in _RELATIONSHIPS:
        found.append(("relationship", "INVALID_FORMAT"))
    share, share_errors = _decimal_field(changes, "share_percent")
    if share is not None and not Decimal(1) <= share <= Decimal(100):
        share_errors = [("share_percent", "OUT_OF_RANGE")]
    return found + share_errors


def _sum_insured_findings(_policy: Policy, changes: Mapping[str, Any]) -> list[Finding]:
    return _decimal_field(changes, "new_sum_insured")[1]


_SHAPE_CHECKS: Final[
    Mapping[EndorsementType, Callable[[Policy, Mapping[str, Any]], list[Finding]]]
] = {
    EndorsementType.CHANGE_ADDRESS: _address_findings,
    EndorsementType.ADD_NOMINEE: _nominee_findings,
    EndorsementType.CHANGE_SUM_INSURED: _sum_insured_findings,
}


def _share_total(policy: Policy) -> Decimal:
    return sum((Decimal(str(n.get("share_percent", 0))) for n in policy.nominees), Decimal(0))


def _raise(findings: list[Finding]) -> None:
    if findings:
        raise ValidationError(
            "Endorsement validation failed",
            [{"field": field, "code": code} for field, code in findings],
        )


class EndorsementService(ApplicationReader):
    """Previews and applies endorsements; the service owns the transaction (AC-06)."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._policies = PolicyRepository(session)
        self._lifecycle = PolicyLifecycleRepository(session)
        self._audit = AuditService(session)

    def preview(
        self,
        policy_number: str,
        endorsement_type: EndorsementType,
        changes: Mapping[str, Any],
        actor: ActingActor,
    ) -> EndorsementResultView:
        """Validate and price the endorsement; persists nothing."""
        policy = self._load(policy_number, actor)
        plan = self._plan(policy, endorsement_type, changes)
        return self._view(policy, endorsement_type, plan, preview=True)

    def apply(
        self,
        policy_number: str,
        endorsement_type: EndorsementType,
        changes: Mapping[str, Any],
        actor: ActingActor,
    ) -> EndorsementResultView:
        """Apply the endorsement in one transaction: all writes commit together or not at all."""
        try:
            policy = self._load(policy_number, actor)
            plan = self._plan(policy, endorsement_type, changes)
            row = self._lifecycle.add_endorsement(
                policy_id=policy.id,
                endorsement_type=endorsement_type,
                before=plan.before,
                after=plan.after,
                premium_delta=plan.premium_delta,
                rule_version=plan.rule_version,
                endorsement_date=plan.endorsement_date,
                actor_id=actor.actor_id,
            )
            self._write_policy(policy, endorsement_type, plan, actor)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return self._view(
            policy, endorsement_type, plan, preview=False, id_=row.id, created_at=row.created_at
        )

    def _write_policy(
        self, policy: Policy, kind: EndorsementType, plan: _Plan, actor: ActingActor
    ) -> None:
        """Move the projection, append the transition and audit the action (no commit)."""
        current = PolicyStatus(policy.status)
        self._policies.update_projection(
            policy, status=PolicyStatus.ENDORSED, attributes=plan.attributes
        )
        self._lifecycle.add_transition(
            policy_id=policy.id,
            from_status=current,
            to_status=PolicyStatus.ENDORSED,
            reason=_ENDORSED_REASON + kind.value,
            actor_id=actor.actor_id,
        )
        if actor.role is ActorRole.ADMIN:
            self._audit.record(
                action=AuditAction.ENDORSEMENT_CREATED,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type=AuditEntityType.POLICY,
                entity_id=policy.policy_number,
                detail={"endorsement_type": kind.value, "rule_version": plan.rule_version},
            )

    def _load(self, policy_number: str, actor: ActingActor) -> Policy:
        policy = owned_policy(self._policies, policy_number, actor)
        assert_transition(PolicyStatus(policy.status), PolicyStatus.ENDORSED)
        return policy

    def _plan(self, policy: Policy, kind: EndorsementType, changes: Mapping[str, Any]) -> _Plan:
        rule_set = self.rule_set_for(policy.product, policy.rule_version)
        on = today()
        current: dict[str, Any] = {
            "sum_insured": policy.sum_insured,
            "nominee_share_total": _share_total(policy),
        }
        if kind not in rule_set.endorsement.allowed_types:
            _raise(validate_endorsement(rule_set, kind, current, changes))
        findings = _SHAPE_CHECKS[kind](policy, changes)
        if not findings:
            findings = validate_endorsement(rule_set, kind, current, changes)
        if not policy.effective_date <= on <= policy.expiry_date:
            findings.append(("endorsement_date", "OUTSIDE_TERM"))
        _raise(findings)
        old_inputs = {**policy.rating_inputs, "sum_insured": policy.sum_insured}
        new_inputs = dict(old_inputs)
        if kind is EndorsementType.CHANGE_SUM_INSURED:
            new_inputs["sum_insured"] = Decimal(changes["new_sum_insured"])
        outcome = build_outcome(
            rule_set,
            kind,
            old_inputs,
            new_inputs,
            unused_days(policy.effective_date, policy.expiry_date, on),
            term_days(policy.effective_date, policy.expiry_date),
        )
        premium = (
            to_money(calculate_premium(rule_set, new_inputs).final_amount)
            if kind is EndorsementType.CHANGE_SUM_INSURED
            else policy.premium
        )
        return self._describe(policy, kind, changes, outcome.premium_delta, premium, on)

    @staticmethod
    def _describe(
        policy: Policy,
        kind: EndorsementType,
        changes: Mapping[str, Any],
        delta: Decimal,
        premium: Decimal,
        on: date,
    ) -> _Plan:
        before: dict[str, Any]
        after: dict[str, Any]
        if kind is EndorsementType.CHANGE_SUM_INSURED:
            new_si = to_money(Decimal(changes["new_sum_insured"]))
            before = {"sum_insured": str(policy.sum_insured), "premium": str(policy.premium)}
            after = {"sum_insured": str(new_si), "premium": str(premium)}
            attributes: dict[str, Any] = {"sum_insured": new_si, "premium": premium}
        elif kind is EndorsementType.CHANGE_ADDRESS:
            before, after = {"address": policy.address}, {"address": changes["address"]}
            attributes = {"address": changes["address"]}
        else:
            nominee = {
                "nominee_name": changes["nominee_name"],
                "relationship": changes["relationship"],
                "share_percent": str(Decimal(changes["share_percent"])),
            }
            nominees = [*policy.nominees, nominee]
            before, after = {"nominees": list(policy.nominees)}, {"nominees": nominees}
            attributes = {"nominees": nominees}
        return _Plan(before, after, attributes, premium, delta, policy.rule_version, on)

    @staticmethod
    def _view(
        policy: Policy,
        kind: EndorsementType,
        plan: _Plan,
        *,
        preview: bool,
        id_: str | None = None,
        created_at: datetime | None = None,
    ) -> EndorsementResultView:
        return EndorsementResultView(
            policy_number=policy.policy_number,
            endorsement_type=kind.value,
            preview=preview,
            before=plan.before,
            after=plan.after,
            new_premium=plan.new_premium,
            premium_delta=plan.premium_delta,
            rule_version=plan.rule_version,
            endorsement_date=plan.endorsement_date,
            endorsement_id=id_,
            created_at=created_at,
            policy=None if preview else summary_view(policy),
        )
