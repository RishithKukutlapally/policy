"""Shared pytest fixtures and test-environment isolation."""

from __future__ import annotations

import copy
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.config.rule_loader import read_rule_document, rule_file_path
from src.main import create_app
from src.repository.database import Base, create_app_engine
from src.seed import import_published_rule_files
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole, ProductCode

_ENV_VARS_UNDER_TEST = (
    "POLICYFORGE_BUSINESS_DATE",
    "BUSINESS_DATE",
    "POLICYFORGE_DATABASE_URL",
    "DATABASE_URL",
)

#: Synthetic demo actors (docs/conventions.md -> "API / auth stub").
ACTOR_IDS: dict[ActorRole, str] = {
    ActorRole.CUSTOMER: "cust-001",
    ActorRole.UNDERWRITER: "uw-001",
    ActorRole.ADMIN: "admin-001",
}


def actor_headers(role: ActorRole, actor_id: str | None = None) -> dict[str, str]:
    """Actor headers for ``role`` using the canonical demo actor id."""
    return {"X-Actor-Id": actor_id or ACTOR_IDS[role], "X-Actor-Role": role.value}


def rule_body(
    product: ProductCode = ProductCode.MOTOR,
    *,
    base_rate: str = "0.0320",
    effective_from: str = "2026-11-01",
) -> dict[str, Any]:
    """A schema-valid rule-file body derived from the seeded ``v1`` file of ``product``."""
    document = copy.deepcopy(read_rule_document(rule_file_path(product, 1)))
    document["premium"]["base_rate"] = base_rate
    document["effective_from"] = effective_from
    document.pop("version", None)
    document.pop("status", None)
    return document


@pytest.fixture(autouse=True)
def isolated_environment() -> Iterator[None]:
    """Restore any PolicyForge env var a test mutates, so tests cannot leak into each other."""
    saved = {name: os.environ.get(name) for name in _ENV_VARS_UNDER_TEST}
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture(name="seeded_engine")
def _seeded_engine(tmp_path: Path) -> Iterator[Engine]:
    """A temp-file SQLite engine holding the three seeded PUBLISHED v1 rule sets."""
    engine = create_app_engine("sqlite:///" + (tmp_path / "policyforge-test.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        import_published_rule_files(session)
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture(name="seeded_session")
def _seeded_session(seeded_engine: Engine) -> Iterator[Session]:
    """A session on the seeded temp database."""
    with Session(seeded_engine) as session:
        yield session


@pytest.fixture(name="api_client")
def _api_client(seeded_engine: Engine) -> Iterator[TestClient]:
    """A ``TestClient`` whose service sessions live on the seeded temp database."""
    app = create_app()

    def _session_override() -> Iterator[Session]:
        with Session(seeded_engine) as session:
            yield session

    app.dependency_overrides[get_service_session] = _session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
