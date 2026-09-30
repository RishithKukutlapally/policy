"""Product-catalog use cases: list products, list versions, draft, replace and publish (E2-S3).

Admins change rates and rules with zero code changes (AC-11): a rule-file JSON body becomes a
DRAFT ``rule_set_versions`` row, may be replaced while it stays DRAFT (DEC-009) and is finally
published, which makes it the product's active version (AC-02). Nothing is ever updated or
deleted — every state change appends a row (NFR-02) — and every mutation writes exactly one
audit record carrying the acting admin's id (NFR-04).

The service owns its transaction and commits once; it raises the typed errors of
`src.types.errors` (never HTTP types) and logs opaque ids only (NFR-03).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Final, Protocol

from sqlalchemy.orm import Session

from src.config.rule_body_validator import content_sha256, validated_rule_document
from src.lib.logging import get_logger
from src.repository.models import AuditAction, AuditEntityType, RuleSetVersion
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.service.audit_service import AuditService
from src.types.enums import ActorRole, ProductCode, RuleSetStatus
from src.types.errors import (
    DraftAlreadyOpenError,
    NotFoundError,
    VersionImmutableError,
)

#: Customer-facing product names (`specs/design/api-contracts.md` §2.2).
PRODUCT_DISPLAY_NAMES: Final[Mapping[ProductCode, str]] = {
    ProductCode.TERM_LIFE: "Term Life",
    ProductCode.MOTOR: "Motor",
    ProductCode.HOUSEHOLD: "Household",
}

DEFAULT_CURRENCY: Final = "INR"

_AUDIT_ACTIONS: Final[Mapping[RuleSetStatus, AuditAction]] = {
    RuleSetStatus.PUBLISHED: AuditAction.RULE_VERSION_PUBLISHED,
}

_logger = get_logger(__name__)


class ActingActor(Protocol):
    """Structural view of the API layer's ``Actor`` (the service never imports `src.api`)."""

    @property
    def actor_id(self) -> str:
        """Opaque id of the caller, recorded on the row and in the audit trail."""

    @property
    def role(self) -> ActorRole:
        """Role the caller acts in; audited alongside the actor id (NFR-04)."""


@dataclass(frozen=True, slots=True)
class ProductView:
    """One `GET /api/products` entry: the product and its active PUBLISHED version."""

    product: ProductCode
    name: str
    active_version: int | None
    currency: str


@dataclass(frozen=True, slots=True)
class RuleVersionView:
    """One version's current state — the highest-``revision`` row of ``(product, version)``."""

    product: ProductCode
    version: int
    revision: int
    status: RuleSetStatus
    effective_from: date
    is_active: bool
    created_at: datetime
    actor_id: str
    content_sha256: str
    rules: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class MutationResultView:
    """Outcome of a draft, replace or publish call (contract §2.4–2.6)."""

    product: ProductCode
    version: int
    status: RuleSetStatus
    is_active: bool


def _product_code(product: str | ProductCode) -> ProductCode:
    """Parse a product code, raising 404 ``NOT_FOUND`` for an unknown one (no existence leak)."""
    try:
        return ProductCode(product)
    except ValueError:
        raise NotFoundError(f"unknown product {product!r}") from None


def _as_utc(moment: datetime) -> datetime:
    """Treat a naive timestamp as UTC so the API always renders a ``Z`` instant."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


class CatalogService:
    """Product catalog and versioned rule sets — the only writer of ``rule_set_versions``."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._versions = RuleSetVersionRepository(session)
        self._audit = AuditService(session)

    def list_products(self) -> list[ProductView]:
        """Every product with its active PUBLISHED version, or ``None`` when it has none (AC-02)."""
        return [self._product_view(product) for product in ProductCode]

    def list_versions(self, product: str | ProductCode) -> list[RuleVersionView]:
        """Current state of every version of one product, ascending (contract §2.3)."""
        code = _product_code(product)
        active = self._versions.active_for_product(code)
        active_version = None if active is None else active.version
        return [
            self._version_view(row, is_active=row.version == active_version)
            for row in self._current_rows(code)
        ]

    def create_draft(
        self, product: str | ProductCode, rules: Mapping[str, Any], actor: ActingActor
    ) -> MutationResultView:
        """Append revision 1 of the next version as a DRAFT (AC-11)."""
        code = _product_code(product)
        current = self._current_rows(code)
        open_draft = next((r for r in current if r.status == RuleSetStatus.DRAFT.value), None)
        if open_draft is not None:
            raise DraftAlreadyOpenError(
                f"{code.value} already has an open DRAFT (v{open_draft.version})"
            )
        version = max((row.version for row in current), default=0) + 1
        document = validated_rule_document(rules, code, version, RuleSetStatus.DRAFT)
        return self._append(code, version, RuleSetStatus.DRAFT, document, actor)

    def replace_draft(
        self,
        product: str | ProductCode,
        version: int,
        rules: Mapping[str, Any],
        actor: ActingActor,
    ) -> MutationResultView:
        """Append the next revision of an open DRAFT with a new body (DEC-009, contract §2.5)."""
        code = _product_code(product)
        self._open_draft_row(code, version)
        document = validated_rule_document(rules, code, version, RuleSetStatus.DRAFT)
        return self._append(code, version, RuleSetStatus.DRAFT, document, actor)

    def publish(
        self, product: str | ProductCode, version: int, actor: ActingActor
    ) -> MutationResultView:
        """Append the PUBLISHED row of an open DRAFT, making it the active version (AC-11)."""
        code = _product_code(product)
        row = self._open_draft_row(code, version)
        document = validated_rule_document(
            row.content, code, version, RuleSetStatus.PUBLISHED, check_declared_fields=False
        )
        return self._append(code, version, RuleSetStatus.PUBLISHED, document, actor)

    def _current_rows(self, product: ProductCode) -> list[RuleSetVersion]:
        """The highest-``revision`` row of each version, ascending by version (DEC-013)."""
        latest: dict[int, RuleSetVersion] = {}
        for row in self._versions.list_for_product(product):
            latest[row.version] = row
        return [latest[version] for version in sorted(latest)]

    def _open_draft_row(self, product: ProductCode, version: int) -> RuleSetVersion:
        """The current row of ``(product, version)``; 404 when absent, 409 when PUBLISHED."""
        row = next((r for r in self._current_rows(product) if r.version == version), None)
        if row is None:
            raise NotFoundError(f"no version {version} for product {product.value}")
        if row.status == RuleSetStatus.PUBLISHED.value:
            raise VersionImmutableError(
                f"{product.value} v{version} is PUBLISHED and can no longer change"
            )
        return row

    def _append(
        self,
        product: ProductCode,
        version: int,
        status: RuleSetStatus,
        document: Mapping[str, Any],
        actor: ActingActor,
    ) -> MutationResultView:
        """Append one row plus its audit record and commit the single transaction (NFR-02/04)."""
        digest = content_sha256(document)
        row = self._versions.add(
            product=product,
            version=version,
            status=status,
            content=document,
            content_sha256=digest,
            actor_id=actor.actor_id,
        )
        detail = {
            "product": product.value,
            "version": version,
            "revision": row.revision,
            "status": status.value,
            "content_sha256": digest,
        }
        self._audit.record(
            action=_audit_action(status, row.revision),
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type=AuditEntityType.RULE_SET_VERSION,
            entity_id=f"{product.value}:v{version}",
            detail=detail,
        )
        active = self._versions.active_for_product(product)
        is_active = active is not None and active.version == version
        self._session.commit()
        _logger.info("rule version appended", extra=detail)
        return MutationResultView(
            product=product, version=version, status=status, is_active=is_active
        )

    def _product_view(self, product: ProductCode) -> ProductView:
        """Build the `GET /api/products` entry for one product."""
        active = self._versions.active_for_product(product)
        current = self._current_rows(product)
        source = active or (current[-1] if current else None)
        currency = DEFAULT_CURRENCY if source is None else str(source.content["currency"])
        return ProductView(
            product=product,
            name=PRODUCT_DISPLAY_NAMES[product],
            active_version=None if active is None else active.version,
            currency=currency,
        )

    def _version_view(self, row: RuleSetVersion, *, is_active: bool) -> RuleVersionView:
        """Project one stored row onto the read model the API serialises."""
        return RuleVersionView(
            product=ProductCode(row.product),
            version=row.version,
            revision=row.revision,
            status=RuleSetStatus(row.status),
            effective_from=row.effective_from,
            is_active=is_active,
            created_at=_as_utc(row.created_at),
            actor_id=row.actor_id,
            content_sha256=row.content_sha256,
            rules=dict(row.content),
        )


def _audit_action(status: RuleSetStatus, revision: int) -> AuditAction:
    """Pick the audit action: publish, first draft, or a DEC-009 draft replacement."""
    published = _AUDIT_ACTIONS.get(status)
    if published is not None:
        return published
    if revision == 1:
        return AuditAction.RULE_VERSION_DRAFT_CREATED
    return AuditAction.RULE_VERSION_DRAFT_REPLACED
