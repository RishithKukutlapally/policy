"""Quote orchestration: resolve the active rule version, validate, price, persist (AC-01/12/13).

The premium comes only from a PUBLISHED ``rule_set_versions`` row; there is no fallback to a
DRAFT or to a file on disk. Quotes are re-priced on their *recorded* version (AC-13). Raw inputs
are never logged (NFR-03).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Final, Protocol

from sqlalchemy.orm import Session

from src.config.rule_loader import build_rule_set
from src.domain.application_validator import validate_application
from src.domain.money import to_money
from src.domain.premium_calculator import PremiumBreakdown, calculate_premium
from src.repository.models import Quote, RuleSetVersion
from src.repository.quote_repository import QuoteRepository
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.types.enums import ActorRole, ProductCode, RuleSetStatus
from src.types.errors import NoPublishedVersionError, NotFoundError, ValidationError
from src.types.rules import RuleSet

_ALLOWED_FIELDS: Final[dict[ProductCode, frozenset[str]]] = {
    ProductCode.TERM_LIFE: frozenset({"sum_insured", "age", "term_years", "smoker"}),
    ProductCode.MOTOR: frozenset(
        {"sum_insured", "owner_age", "vehicle_age_years", "engine_cc", "zone", "ncb_percent"}
    ),
    ProductCode.HOUSEHOLD: frozenset(
        {
            "sum_insured",
            "proposer_age",
            "construction_type",
            "in_flood_zone",
            "has_security_system",
        }
    ),
}
_TERM_YEARS_MIN: Final = 5
_TERM_YEARS_MAX: Final = 30


class ActingActor(Protocol):
    """Structural view of the API layer's ``Actor`` (the service never imports `src.api`)."""

    @property
    def actor_id(self) -> str:
        """Opaque id of the caller."""
        ...

    @property
    def role(self) -> ActorRole:
        """Role the caller acts in."""
        ...


class QuoteValidationError(ValidationError):
    """Quote inputs failed validation; ``details`` lists every failing field."""


@dataclass(frozen=True, slots=True)
class QuoteView:
    """Read model of a stored quote handed to the API layer."""

    id: str
    product: str
    rule_version: int
    inputs: dict[str, Any]
    sum_insured: Decimal
    premium: Decimal
    currency: str
    actor_id: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: Quote) -> QuoteView:
        """Copy the fields of a stored quote."""
        return cls(
            id=row.id,
            product=row.product,
            rule_version=row.rule_version,
            inputs=dict(row.inputs),
            sum_insured=row.sum_insured,
            premium=row.premium,
            currency=row.currency,
            actor_id=row.actor_id,
            created_at=row.created_at,
        )


@dataclass(frozen=True, slots=True)
class RepriceResult:
    """Outcome of re-pricing a stored quote on its recorded rule version."""

    quote_id: str
    rule_version: int
    stored_premium: Decimal
    recomputed_premium: Decimal

    @property
    def matches(self) -> bool:
        """True when the recomputed premium equals the stored one exactly."""
        return self.stored_premium == self.recomputed_premium


def _money(value: Decimal) -> str:
    """Two-decimal string for a money value."""
    return str(to_money(value))


def _breakdown_json(breakdown: PremiumBreakdown) -> dict[str, Any]:
    """JSON-safe breakdown: every Decimal as a string (NFR-01)."""
    return {
        "base": str(breakdown.base),
        "steps": [{"factor": s.factor, "multiplier": str(s.multiplier)} for s in breakdown.steps],
        "raw_amount": str(breakdown.raw_amount),
        "minimum_premium": str(breakdown.minimum_premium),
        "final_amount": _money(breakdown.final_amount),
    }


def _is_json_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def field_errors(rule_set: RuleSet, inputs: Mapping[str, Any]) -> list[dict[str, str]]:
    """Every failing input field as ``{field, code}``; empty when the inputs are valid."""
    product = rule_set.product
    allowed = _ALLOWED_FIELDS[product]
    errors = [{"field": name, "code": "UNKNOWN_FIELD"} for name in sorted(set(inputs) - allowed)]
    risk = {k: v for k, v in inputs.items() if k in allowed}
    if _is_json_number(risk.get("sum_insured")):
        errors.append({"field": "sum_insured", "code": "MONEY_MUST_BE_STRING"})
        risk.pop("sum_insured")
    health = {"has_pre_existing_condition": False}
    for finding in validate_application(rule_set, {}, risk, health):
        if not finding.field.startswith(("kyc.", "health_declaration")):
            errors.append({"field": finding.field, "code": finding.code})
    term = risk.get("term_years")
    term_bad = isinstance(term, int) and not _TERM_YEARS_MIN <= term <= _TERM_YEARS_MAX
    if product is ProductCode.TERM_LIFE and term_bad:
        errors.append({"field": "term_years", "code": "OUT_OF_RANGE"})
    return errors


class QuoteService:
    """Creates, reads and re-prices quotes; the only writer of ``quotes``."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._quotes = QuoteRepository(session)
        self._versions = RuleSetVersionRepository(session)

    def create_quote(
        self, product: ProductCode | str, inputs: Mapping[str, Any], actor: ActingActor
    ) -> QuoteView:
        """Price ``inputs`` on the active PUBLISHED version and persist the quote."""
        code = self._product(product)
        row = self._versions.active_for_product(code)
        if row is None:
            raise NoPublishedVersionError(f"Product {code.value} has no PUBLISHED rule version")
        rule_set = self._rule_set(row)
        errors = field_errors(rule_set, inputs)
        if errors:
            raise QuoteValidationError("Quote inputs failed validation", errors)
        normalised = self._normalise(inputs)
        breakdown = calculate_premium(rule_set, normalised)
        quote = self._quotes.add(
            product=code.value,
            rule_version=row.version,
            inputs=normalised,
            sum_insured=Decimal(str(normalised["sum_insured"])),
            premium=breakdown.final_amount,
            breakdown=_breakdown_json(breakdown),
            actor_id=actor.actor_id,
        )
        self._session.commit()
        return QuoteView.from_row(quote)

    def get_quote(self, quote_id: str, actor: ActingActor) -> QuoteView:
        """The quote, or 404 when unknown or another customer's."""
        return QuoteView.from_row(self._owned_row(quote_id, actor))

    def _owned_row(self, quote_id: str, actor: ActingActor) -> Quote:
        quote = self._quotes.get(quote_id)
        if quote is None or (actor.role is ActorRole.CUSTOMER and quote.actor_id != actor.actor_id):
            raise NotFoundError("Quote not found")
        return quote

    def reprice(self, quote_id: str, actor: ActingActor) -> RepriceResult:
        """Recompute on the quote's recorded rule version (AC-13); never mutates the quote."""
        quote = self._owned_row(quote_id, actor)
        row = self._recorded_row(ProductCode(quote.product), quote.rule_version)
        breakdown = calculate_premium(self._rule_set(row), quote.inputs)
        return RepriceResult(
            quote_id=quote.id,
            rule_version=quote.rule_version,
            stored_premium=quote.premium,
            recomputed_premium=breakdown.final_amount,
        )

    @staticmethod
    def _product(product: ProductCode | str) -> ProductCode:
        try:
            return ProductCode(product)
        except ValueError:
            raise NotFoundError("Unknown product") from None

    @staticmethod
    def _normalise(inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Canonical inputs: money and NCB kept as strings so they round-trip through JSON."""
        result = dict(inputs)
        result["sum_insured"] = str(result["sum_insured"])
        if "ncb_percent" in result:
            result["ncb_percent"] = str(result["ncb_percent"])
        return result

    def _recorded_row(self, product: ProductCode, version: int) -> RuleSetVersion:
        """Latest PUBLISHED row of the recorded ``(product, version)``."""
        rows = [
            r
            for r in self._versions.list_for_product(product)
            if r.version == version and r.status == RuleSetStatus.PUBLISHED.value
        ]
        if not rows:
            raise NoPublishedVersionError(f"Recorded rule version {version} is unavailable")
        return max(rows, key=lambda r: r.revision)

    @staticmethod
    def _rule_set(row: RuleSetVersion) -> RuleSet:
        return build_rule_set(row.content, label=f"{row.product} v{row.version}")
