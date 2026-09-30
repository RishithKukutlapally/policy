"""Integration tests: the append-only ``rule_set_versions`` repository (DEC-013, NFR-02)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config.rule_loader import (
    load_rule_file,
    read_rule_document,
    rule_file_path,
    sha256_of_file,
)
from src.repository.database import Base, create_app_engine
from src.repository.models import RuleSetVersion
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.types.enums import ProductCode, RuleSetStatus

pytestmark = pytest.mark.integration

EXPECTED_PUBLIC_METHODS = {"add", "latest_status", "list_for_product", "active_for_product"}
MUTATING_NAMES = ("update", "delete", "remove", "save", "merge", "set", "upsert")


@pytest.fixture(name="session")
def _session() -> Iterator[Session]:
    engine = create_app_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _content(product: ProductCode, version: int) -> dict[str, object]:
    path = rule_file_path(product, 1)
    document = dict(read_rule_document(path))
    document["version"] = version
    return document


def _add(
    session: Session,
    product: ProductCode,
    version: int,
    status: RuleSetStatus,
) -> RuleSetVersion:
    repository = RuleSetVersionRepository(session)
    return repository.add(
        product=product,
        version=version,
        status=status,
        content=_content(product, version),
        content_sha256=sha256_of_file(rule_file_path(product, 1)),
        actor_id="admin-001",
    )


def test_repository_is_append_only() -> None:
    """AC-6: the public surface is exactly ``add`` plus the three read methods."""
    public = {
        name
        for name in vars(RuleSetVersionRepository)
        if not name.startswith("_") and callable(getattr(RuleSetVersionRepository, name))
    }
    assert public == EXPECTED_PUBLIC_METHODS
    assert not [name for name in public if name.startswith(MUTATING_NAMES)]


def test_first_row_gets_revision_one(session: Session) -> None:
    row = _add(session, ProductCode.MOTOR, 2, RuleSetStatus.DRAFT)
    assert row.revision == 1
    assert row.effective_from.isoformat() == "2026-01-01"
    assert len(row.content_sha256) == 64


def test_draft_replace_appends_the_next_revision(session: Session) -> None:
    _add(session, ProductCode.MOTOR, 2, RuleSetStatus.DRAFT)
    replacement = _add(session, ProductCode.MOTOR, 2, RuleSetStatus.DRAFT)
    assert replacement.revision == 2
    rows = RuleSetVersionRepository(session).list_for_product(ProductCode.MOTOR)
    assert [row.revision for row in rows] == [1, 2]


def test_publishing_appends_a_row_and_becomes_the_latest_status(session: Session) -> None:
    _add(session, ProductCode.MOTOR, 2, RuleSetStatus.DRAFT)
    published = _add(session, ProductCode.MOTOR, 2, RuleSetStatus.PUBLISHED)
    assert published.revision == 2
    repository = RuleSetVersionRepository(session)
    assert repository.latest_status(ProductCode.MOTOR, 2) is RuleSetStatus.PUBLISHED
    assert repository.latest_status(ProductCode.MOTOR, 7) is None


def test_second_published_row_for_the_same_version_is_rejected(session: Session) -> None:
    _add(session, ProductCode.MOTOR, 2, RuleSetStatus.PUBLISHED)
    with pytest.raises(IntegrityError):
        _add(session, ProductCode.MOTOR, 2, RuleSetStatus.PUBLISHED)
    session.rollback()


def test_active_for_product_picks_the_highest_published_version(session: Session) -> None:
    repository = RuleSetVersionRepository(session)
    assert repository.active_for_product(ProductCode.MOTOR) is None
    _add(session, ProductCode.MOTOR, 1, RuleSetStatus.PUBLISHED)
    _add(session, ProductCode.MOTOR, 2, RuleSetStatus.DRAFT)
    active = repository.active_for_product(ProductCode.MOTOR)
    assert active is not None and active.version == 1
    _add(session, ProductCode.MOTOR, 2, RuleSetStatus.PUBLISHED)
    active = repository.active_for_product(ProductCode.MOTOR)
    assert active is not None and active.version == 2


def test_list_for_product_is_scoped_to_one_product(session: Session) -> None:
    _add(session, ProductCode.MOTOR, 1, RuleSetStatus.PUBLISHED)
    _add(session, ProductCode.HOUSEHOLD, 1, RuleSetStatus.PUBLISHED)
    repository = RuleSetVersionRepository(session)
    assert [row.product for row in repository.list_for_product(ProductCode.HOUSEHOLD)] == [
        ProductCode.HOUSEHOLD.value
    ]


def test_stored_content_round_trips_into_a_rule_set(session: Session) -> None:
    row = _add(session, ProductCode.TERM_LIFE, 1, RuleSetStatus.PUBLISHED)
    session.expire_all()
    stored = session.get(RuleSetVersion, row.id)
    assert stored is not None
    assert stored.content["premium"]["base_rate"] == "0.0015"
    assert isinstance(stored.content["premium"]["minimum_premium"], str)
    assert load_rule_file(ProductCode.TERM_LIFE, 1).premium.base_rate is not None


def test_table_has_no_float_columns() -> None:
    columns = inspect(RuleSetVersion).columns
    assert not [c for c in columns if "FLOAT" in str(c.type).upper()]
