"""AC-02 — three products, each with a distinct PUBLISHED v1 rule set and a persisted row."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from src.config.rule_loader import discover_rule_files, load_rule_file
from src.repository.database import Base, create_app_engine
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.seed import import_published_rule_files
from src.types.enums import ProductCode, RuleSetStatus

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = (ProductCode.TERM_LIFE, ProductCode.MOTOR, ProductCode.HOUSEHOLD)


@pytest.fixture(name="session")
def _session() -> Iterator[Session]:
    engine = create_app_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.mark.ac("AC-02")
def test_ac02_every_product_loads_a_published_v1_rule_set() -> None:
    for product in PRODUCTS:
        rule_set = load_rule_file(product, 1)
        assert rule_set.product is product
        assert rule_set.version == 1
        assert rule_set.status is RuleSetStatus.PUBLISHED


@pytest.mark.ac("AC-02")
def test_ac02_each_product_has_a_distinct_base_rate_and_factor_set() -> None:
    rule_sets = {product: load_rule_file(product, 1) for product in PRODUCTS}
    base_rates = {rs.premium.base_rate for rs in rule_sets.values()}
    assert len(base_rates) == len(PRODUCTS)
    assert all(isinstance(rate, Decimal) for rate in base_rates)
    factor_key_sets = [frozenset(rs.premium.factor_keys) for rs in rule_sets.values()]
    assert len(set(factor_key_sets)) == len(PRODUCTS)
    assert factor_key_sets[1] == frozenset(
        {"vehicle_age_bands", "engine_cc_bands", "ncb_discounts", "zone_rates"}
    )


@pytest.mark.ac("AC-02")
def test_ac02_minimum_premiums_are_distinct_decimals() -> None:
    minimums = {load_rule_file(p, 1).premium.minimum_premium for p in PRODUCTS}
    assert minimums == {Decimal("3000.00"), Decimal("2500.00"), Decimal("1500.00")}


@pytest.mark.ac("AC-02")
def test_ac02_discovery_reports_one_published_file_per_product() -> None:
    by_product = {ref.product: ref for ref in discover_rule_files()}
    assert set(by_product) == set(PRODUCTS)
    assert all(ref.version == 1 for ref in by_product.values())


@pytest.mark.ac("AC-02")
def test_ac02_seed_persists_a_published_row_per_product(session: Session) -> None:
    assert import_published_rule_files(session) == 3
    repository = RuleSetVersionRepository(session)
    for product in PRODUCTS:
        active = repository.active_for_product(product)
        assert active is not None
        assert active.version == 1
        assert active.status == RuleSetStatus.PUBLISHED.value


@pytest.mark.ac("AC-02")
def test_ac02_migration_creates_rule_set_versions_with_dec013_constraints(tmp_path: Path) -> None:
    db_path = tmp_path / "ac02.db"
    url = "sqlite:" + "//" + "/" + db_path.as_posix()
    env = dict(os.environ, POLICYFORGE_DATABASE_URL=url, DATABASE_URL=url)
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgrade.returncode == 0, upgrade.stderr
    heads = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert len([line for line in heads.stdout.splitlines() if line.strip()]) == 1

    engine = create_engine(url)
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("rule_set_versions")}
    assert columns == {
        "id",
        "product",
        "version",
        "revision",
        "status",
        "effective_from",
        "content",
        "content_sha256",
        "actor_id",
        "created_at",
    }
    unique = {
        uc["name"]: list(uc["column_names"])
        for uc in inspector.get_unique_constraints("rule_set_versions")
    }
    assert unique["uq_rule_set_versions_product_version_revision"] == [
        "product",
        "version",
        "revision",
    ]
    with engine.connect() as connection:
        sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE name = 'uq_rule_set_versions_published'"
        ).scalar_one()
    assert "UNIQUE" in sql.upper()
    assert "WHERE status = 'PUBLISHED'" in sql
    engine.dispose()
