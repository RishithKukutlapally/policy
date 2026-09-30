"""Product-catalog request/response DTOs (contract §2.2–2.6; `frontend/src/types/catalog.ts`).

Money and rates cross the wire as JSON **strings**: the rule body is passed through exactly as it
was validated and stored, so nothing is ever re-rendered as a JSON number (NFR-01). Timestamps are
ISO-8601 UTC with a trailing ``Z``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from src.service.catalog_service import MutationResultView, ProductView, RuleVersionView
from src.types.enums import ProductCode, RuleSetStatus

#: A full rule-file JSON body; its shape is validated by the rule-file JSON schema, not pydantic.
RuleFileBody = dict[str, Any]

_UTC_SUFFIX: Final = "Z"


def iso_instant(moment: datetime) -> str:
    """Render a UTC instant as ``2026-01-01T00:00:00Z``."""
    return moment.isoformat().replace("+00:00", _UTC_SUFFIX)


class ProductSummaryResponse(BaseModel):
    """One `GET /api/products` entry (contract §2.2)."""

    model_config = ConfigDict(frozen=True)

    product: ProductCode
    name: str
    active_version: int | None
    currency: str

    @classmethod
    def from_view(cls, view: ProductView) -> ProductSummaryResponse:
        """Build the DTO from the service read model."""
        return cls(
            product=view.product,
            name=view.name,
            active_version=view.active_version,
            currency=view.currency,
        )


class RuleSetVersionResponse(BaseModel):
    """One `GET /api/products/{product}/versions` entry (contract §2.3)."""

    model_config = ConfigDict(frozen=True)

    product: ProductCode
    version: int
    revision: int
    status: RuleSetStatus
    effective_from: date
    is_active: bool
    created_at: str
    actor_id: str
    rules: RuleFileBody

    @classmethod
    def from_view(cls, view: RuleVersionView) -> RuleSetVersionResponse:
        """Build the DTO from the service read model, keeping the rule body verbatim."""
        return cls(
            product=view.product,
            version=view.version,
            revision=view.revision,
            status=view.status,
            effective_from=view.effective_from,
            is_active=view.is_active,
            created_at=iso_instant(view.created_at),
            actor_id=view.actor_id,
            rules=dict(view.rules),
        )


class RuleVersionMutationResponse(BaseModel):
    """201/200 body of the DRAFT create and replace endpoints (contract §2.4, §2.5)."""

    model_config = ConfigDict(frozen=True)

    product: ProductCode
    version: int
    status: RuleSetStatus

    @classmethod
    def from_view(cls, view: MutationResultView) -> RuleVersionMutationResponse:
        """Build the DTO from the service mutation result."""
        return cls(product=view.product, version=view.version, status=view.status)


class PublishResponse(RuleVersionMutationResponse):
    """200 body of the publish endpoint — the version is now the active one (contract §2.6)."""

    is_active: bool

    @classmethod
    def from_view(cls, view: MutationResultView) -> PublishResponse:
        """Build the DTO from the service mutation result."""
        return cls(
            product=view.product,
            version=view.version,
            status=view.status,
            is_active=view.is_active,
        )
