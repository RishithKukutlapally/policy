"""Shared helpers for the quote-engine tests (synthetic inputs only)."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from src.repository.models import RuleSetVersion
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.types.enums import ProductCode, RuleSetStatus
from tests.conftest import rule_body

MOTOR_INPUTS: dict[str, Any] = {
    "sum_insured": "500000.00",
    "owner_age": 35,
    "vehicle_age_years": 3,
    "engine_cc": 1200,
    "zone": "A",
    "ncb_percent": "20",
}


def motor_request(**overrides: Any) -> dict[str, Any]:
    """POST /api/quotes body for the golden MOTOR profile with optional input overrides."""
    return {"product": "MOTOR", "inputs": {**MOTOR_INPUTS, **overrides}}


def publish_version(
    engine: Engine, product: ProductCode, version: int, base_rate: str, *, published: bool = True
) -> None:
    """Append a version row (PUBLISHED or DRAFT) with a different base rate."""
    body = rule_body(product, base_rate=base_rate)
    body["version"] = version
    body["status"] = "PUBLISHED" if published else "DRAFT"
    status = RuleSetStatus.PUBLISHED if published else RuleSetStatus.DRAFT
    with Session(engine) as session:
        RuleSetVersionRepository(session).add(
            product=product,
            version=version,
            status=status,
            content=body,
            content_sha256=hashlib.sha256(base_rate.encode()).hexdigest(),
            actor_id="admin-001",
        )
        session.commit()


def drop_product_versions(engine: Engine, product: ProductCode) -> None:
    """Test setup only: remove every seeded version row of ``product``."""
    with Session(engine) as session:
        session.execute(delete(RuleSetVersion).where(RuleSetVersion.product == product.value))
        session.commit()
