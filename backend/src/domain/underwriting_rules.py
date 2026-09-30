"""Pure automatic underwriting decision engine (AC-04).

Evaluates the active rule set's `underwriting.rules` in file order and returns the
most severe decision with every matching reason code. No logging, I/O or clock.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.domain.condition import evaluate_condition
from src.types.enums import Decision, ProductCode
from src.types.errors import ValidationError
from src.types.rules import RuleSet

_SEVERITY: Mapping[Decision, int] = {
    Decision.AUTO_BIND: 0,
    Decision.MANUAL_REVIEW: 1,
    Decision.DECLINE: 2,
}


class UnknownReasonCodeError(ValidationError):
    """A rule references a reason code missing from `underwriting.reason_codes`."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(
            f"underwriting rule references undefined reason code {reason_code}",
            [{"field": "underwriting.rules.reason_code", "code": "UNKNOWN_REASON_CODE"}],
        )


@dataclass(frozen=True, slots=True)
class UnderwritingOutcome:
    """Decision, sorted reason codes and the rule version that produced them."""

    decision: Decision
    reason_codes: tuple[str, ...]
    rule_version: int


def _context(rule_set: RuleSet, inputs: Mapping[str, Any]) -> dict[str, object]:
    """Evaluation context: inputs with Decimal money and derived fields."""
    context: dict[str, object] = dict(inputs)
    if "sum_insured" in context:
        context["sum_insured"] = Decimal(str(context["sum_insured"]))
    if rule_set.product is ProductCode.TERM_LIFE:
        if "age" in inputs and "term_years" in inputs:
            context.setdefault("age_at_term_end", int(inputs["age"]) + int(inputs["term_years"]))
        context.setdefault("has_pre_existing_condition", False)
    return context


def decide(rule_set: RuleSet, application_inputs: Mapping[str, Any]) -> UnderwritingOutcome:
    """Return the most severe matching decision; AUTO_BIND with no codes if none match."""
    context = _context(rule_set, application_inputs)
    known = rule_set.underwriting.reason_codes
    decision = Decision.AUTO_BIND
    codes: set[str] = set()
    for rule in rule_set.underwriting.rules:
        if rule.reason_code not in known:
            raise UnknownReasonCodeError(rule.reason_code)
        if evaluate_condition(rule.when, context):
            codes.add(rule.reason_code)
            if _SEVERITY[rule.decision] > _SEVERITY[decision]:
                decision = rule.decision
    return UnderwritingOutcome(decision, tuple(sorted(codes)), rule_set.version)


evaluate_underwriting = decide
