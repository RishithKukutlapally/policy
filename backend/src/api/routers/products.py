"""Product-catalog router — the five endpoints of `specs/design/api-contracts.md` §2.2–2.6.

Reads are open to every header role; every write is ADMIN only and audited by the service with the
admin's actor id (AC-02, AC-11, AC-22, NFR-04). The router only maps HTTP to one service call;
typed errors from `src.types.errors` are turned into the canonical envelope by the handlers
registered in `src.api.errors`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.orm import Session

from src.api.deps import Actor, require_role
from src.api.schemas.catalog import (
    ProductSummaryResponse,
    PublishResponse,
    RuleFileBody,
    RuleSetVersionResponse,
    RuleVersionMutationResponse,
)
from src.service.catalog_service import CatalogService
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole

router = APIRouter(prefix="/products", tags=["products"])

ReadActor = Annotated[
    Actor, Depends(require_role(ActorRole.CUSTOMER, ActorRole.UNDERWRITER, ActorRole.ADMIN))
]
AdminActor = Annotated[Actor, Depends(require_role(ActorRole.ADMIN))]
ServiceSession = Annotated[Session, Depends(get_service_session)]

ProductPath = Annotated[str, Path(description="Product code (TERM_LIFE | MOTOR | HOUSEHOLD)")]
VersionPath = Annotated[int, Path(ge=1, description="Rule-set version number")]
RuleFileRequest = Annotated[RuleFileBody, Body(description="Full rule-file JSON body")]


def _service(session: Session) -> CatalogService:
    """Build the catalog service for one request."""
    return CatalogService(session)


@router.get("", summary="List products with their active rule version")
def list_products(_actor: ReadActor, session: ServiceSession) -> list[ProductSummaryResponse]:
    """Contract §2.2 — ordered TERM_LIFE, MOTOR, HOUSEHOLD (AC-02)."""
    return [ProductSummaryResponse.from_view(view) for view in _service(session).list_products()]


@router.get("/{product}/versions", summary="List a product's rule-set versions")
def list_versions(
    product: ProductPath, _actor: ReadActor, session: ServiceSession
) -> list[RuleSetVersionResponse]:
    """Contract §2.3 — one entry per version, ascending, exactly one active (AC-11)."""
    views = _service(session).list_versions(product)
    return [RuleSetVersionResponse.from_view(view) for view in views]


@router.post("/{product}/versions", status_code=201, summary="Create a DRAFT rule version")
def create_draft(
    product: ProductPath, rules: RuleFileRequest, actor: AdminActor, session: ServiceSession
) -> RuleVersionMutationResponse:
    """Contract §2.4 — ADMIN only; 409 ``DRAFT_ALREADY_OPEN`` when one is already open."""
    view = _service(session).create_draft(product, rules, actor)
    return RuleVersionMutationResponse.from_view(view)


@router.put("/{product}/versions/{version}", summary="Replace an open DRAFT rule version")
def replace_draft(
    product: ProductPath,
    version: VersionPath,
    rules: RuleFileRequest,
    actor: AdminActor,
    session: ServiceSession,
) -> RuleVersionMutationResponse:
    """Contract §2.5 (DEC-009) — appends a new revision; PUBLISHED → 409 ``VERSION_IMMUTABLE``."""
    view = _service(session).replace_draft(product, version, rules, actor)
    return RuleVersionMutationResponse.from_view(view)


@router.post("/{product}/versions/{version}/publish", summary="Publish a DRAFT rule version")
def publish_version(
    product: ProductPath, version: VersionPath, actor: AdminActor, session: ServiceSession
) -> PublishResponse:
    """Contract §2.6 — appends the PUBLISHED row; the version becomes active (AC-11)."""
    return PublishResponse.from_view(_service(session).publish(product, version, actor))
