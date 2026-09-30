"""Catalog service use cases (E2-S3): listing, drafting, replacing and publishing rule versions."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.rule_loader import RuleFileValidationError
from src.service.catalog_service import (
    PRODUCT_DISPLAY_NAMES,
    CatalogService,
    RuleVersionView,
)
from src.types.enums import ActorRole, ProductCode, RuleSetStatus
from src.types.errors import DraftAlreadyOpenError, NotFoundError, VersionImmutableError
from tests.conftest import rule_body

ADMIN = ("admin-001", ActorRole.ADMIN)


class _Actor:
    """Structural stand-in for `src.api.deps.Actor` (the service never imports the API layer)."""

    def __init__(self, actor_id: str, role: ActorRole) -> None:
        self.actor_id = actor_id
        self.role = role


@pytest.fixture(name="service")
def _service(seeded_session: Session) -> CatalogService:
    return CatalogService(seeded_session)


@pytest.fixture(name="admin")
def _admin() -> _Actor:
    return _Actor(*ADMIN)


def _motor(service: CatalogService) -> list[RuleVersionView]:
    return service.list_versions(ProductCode.MOTOR.value)


def test_list_products_returns_three_products_with_active_v1(service: CatalogService) -> None:
    products = service.list_products()
    assert [p.product for p in products] == list(ProductCode)
    assert all(p.active_version == 1 and p.currency == "INR" for p in products)
    assert [p.name for p in products] == [PRODUCT_DISPLAY_NAMES[p] for p in ProductCode]


def test_list_versions_reports_the_seeded_published_version(service: CatalogService) -> None:
    versions = _motor(service)
    assert len(versions) == 1
    only = versions[0]
    assert (only.version, only.revision, only.status) == (1, 1, RuleSetStatus.PUBLISHED)
    assert only.is_active is True
    assert only.actor_id == "SYSTEM"
    assert only.rules["premium"]["minimum_premium"] == "2500.00"


def test_list_versions_rejects_an_unknown_product(service: CatalogService) -> None:
    with pytest.raises(NotFoundError):
        service.list_versions("SPACESHIP")


def test_create_draft_appends_the_next_version_without_changing_the_active_one(
    service: CatalogService, admin: _Actor
) -> None:
    result = service.create_draft(ProductCode.MOTOR.value, rule_body(), admin)
    assert (result.version, result.status, result.is_active) == (2, RuleSetStatus.DRAFT, False)
    assert service.list_products()[1].active_version == 1
    assert [v.version for v in _motor(service)] == [1, 2]


def test_create_draft_twice_raises_draft_already_open(
    service: CatalogService, admin: _Actor
) -> None:
    service.create_draft(ProductCode.MOTOR.value, rule_body(), admin)
    with pytest.raises(DraftAlreadyOpenError):
        service.create_draft(ProductCode.MOTOR.value, rule_body(base_rate="0.0340"), admin)
    assert len(_motor(service)) == 2


def test_create_draft_rejects_a_schema_invalid_body_and_stores_nothing(
    service: CatalogService, admin: _Actor
) -> None:
    body = rule_body()
    body["premium"]["minimum_premium"] = 2500
    with pytest.raises(RuleFileValidationError):
        service.create_draft(ProductCode.MOTOR.value, body, admin)
    assert len(_motor(service)) == 1


def test_create_draft_rejects_a_body_for_another_product(
    service: CatalogService, admin: _Actor
) -> None:
    with pytest.raises(RuleFileValidationError):
        service.create_draft(ProductCode.MOTOR.value, rule_body(ProductCode.HOUSEHOLD), admin)
    assert len(_motor(service)) == 1


def test_create_draft_rejects_a_declared_version_that_is_not_the_next_one(
    service: CatalogService, admin: _Actor
) -> None:
    body = rule_body()
    body["version"] = 7
    with pytest.raises(RuleFileValidationError):
        service.create_draft(ProductCode.MOTOR.value, body, admin)


def test_replace_draft_appends_a_new_revision_of_the_same_version(
    service: CatalogService, admin: _Actor
) -> None:
    service.create_draft(ProductCode.MOTOR.value, rule_body(), admin)
    result = service.replace_draft(ProductCode.MOTOR.value, 2, rule_body(base_rate="0.0330"), admin)
    assert (result.version, result.status) == (2, RuleSetStatus.DRAFT)
    latest = _motor(service)[1]
    assert latest.revision == 2
    assert latest.rules["premium"]["base_rate"] == "0.0330"


def test_replace_draft_on_a_published_version_raises_version_immutable(
    service: CatalogService, admin: _Actor
) -> None:
    with pytest.raises(VersionImmutableError):
        service.replace_draft(ProductCode.MOTOR.value, 1, rule_body(), admin)
    assert len(_motor(service)) == 1


def test_replace_draft_on_an_unknown_version_raises_not_found(
    service: CatalogService, admin: _Actor
) -> None:
    with pytest.raises(NotFoundError):
        service.replace_draft(ProductCode.MOTOR.value, 9, rule_body(), admin)


def test_publish_makes_the_version_active_and_leaves_v1_untouched(
    service: CatalogService, admin: _Actor
) -> None:
    before = _motor(service)[0]
    service.create_draft(ProductCode.MOTOR.value, rule_body(), admin)
    result = service.publish(ProductCode.MOTOR.value, 2, admin)
    assert (result.version, result.status, result.is_active) == (2, RuleSetStatus.PUBLISHED, True)
    versions = _motor(service)
    assert [v.is_active for v in versions] == [False, True]
    assert versions[0].content_sha256 == before.content_sha256
    assert versions[1].rules["status"] == "PUBLISHED"


def test_publish_an_already_published_version_raises_version_immutable(
    service: CatalogService, admin: _Actor
) -> None:
    with pytest.raises(VersionImmutableError):
        service.publish(ProductCode.MOTOR.value, 1, admin)


def test_publish_an_unknown_version_raises_not_found(
    service: CatalogService, admin: _Actor
) -> None:
    with pytest.raises(NotFoundError):
        service.publish(ProductCode.MOTOR.value, 9, admin)


def test_the_service_exposes_no_update_or_delete_operation() -> None:
    """NFR-02: the public surface can only append."""
    public = {name for name in vars(CatalogService) if not name.startswith("_")}
    assert public == {"list_products", "list_versions", "create_draft", "replace_draft", "publish"}


def test_products_without_a_published_version_report_no_active_version(
    seeded_session: Session, admin: _Actor
) -> None:
    """A product whose only version is a DRAFT has ``active_version`` ``None``."""
    seeded_session.execute(text("DELETE FROM rule_set_versions WHERE product = 'HOUSEHOLD'"))
    seeded_session.commit()
    service = CatalogService(seeded_session)
    service.create_draft(ProductCode.HOUSEHOLD.value, rule_body(ProductCode.HOUSEHOLD), admin)
    household = {p.product: p for p in service.list_products()}[ProductCode.HOUSEHOLD]
    assert household.active_version is None
    assert household.currency == "INR"
