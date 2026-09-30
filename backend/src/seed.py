"""Idempotent seed: rule files plus the demo portfolio (AC-02, AC-04, AC-05, NFR-05).

Run with ``python -m src.seed``. Two steps, both idempotent:

1. import every PUBLISHED rule file into ``rule_set_versions``. The import verifies
   `PUBLISHED.lock` **before** touching the database, so a tampered rule file aborts the run with
   nothing written. Rows already present for a ``(product, version)`` are skipped.
2. build the demo portfolio — synthetic customers, quotes, applications (>= 70 % ``AUTO_BIND``)
   and policies in every lifecycle state — by driving the production services
   (:mod:`src.seed_data.portfolio`). It runs only when no application exists yet.

A second run therefore inserts nothing and logs the same counts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.config.rule_loader import (
    RuleFileRef,
    build_rule_set,
    discover_rule_files,
    read_rule_document,
    verify_published_lock,
)
from src.lib.logging import get_logger
from src.repository.database import SessionLocal
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.seed_data.portfolio import seed_portfolio
from src.seed_data.summary import PortfolioSummary
from src.types.enums import RuleSetStatus

__all__ = [
    "PortfolioSummary",
    "import_published_rule_files",
    "run",
    "seed_portfolio",
    "seed_summary",
]

SEED_ACTOR_ID = "SYSTEM"

_logger = get_logger(__name__)


def seed_summary(inserted: int, skipped: int) -> dict[str, Any]:
    """One-line JSON summary payload of a seed run."""
    return {"event": "seed_completed", "inserted": inserted, "skipped": skipped}


def _published_refs(rules_root: Path | None) -> tuple[RuleFileRef, ...]:
    """Every discovered rule file whose declared status is PUBLISHED."""
    return tuple(
        ref for ref in discover_rule_files(rules_root) if ref.status is RuleSetStatus.PUBLISHED
    )


def _import_one(
    repository: RuleSetVersionRepository, ref: RuleFileRef, rules_root: Path | None
) -> bool:
    """Append one PUBLISHED row for ``ref``; return ``False`` when it already exists."""
    if repository.latest_status(ref.product, ref.version) is not None:
        return False
    content = read_rule_document(ref.path)
    rule_set = build_rule_set(
        read_rule_document(ref.path, as_decimal=True), label=ref.path.name, rules_root=rules_root
    )
    repository.add(
        product=rule_set.product,
        version=rule_set.version,
        status=RuleSetStatus.PUBLISHED,
        content=content,
        content_sha256=ref.sha256,
        actor_id=SEED_ACTOR_ID,
        effective_from=rule_set.effective_from,
    )
    return True


def import_published_rule_files(session: Session, rules_root: Path | None = None) -> int:
    """Import every PUBLISHED rule file, returning how many rows were appended (0 when seeded)."""
    verify_published_lock(rules_root)
    repository = RuleSetVersionRepository(session)
    return sum(_import_one(repository, ref, rules_root) for ref in _published_refs(rules_root))


def run(rules_root: Path | None = None) -> dict[str, Any]:
    """Seed the configured database and log one JSON summary line per step."""
    with SessionLocal() as session:
        inserted = import_published_rule_files(session, rules_root)
        session.commit()
        total = len(_published_refs(rules_root))
        summary = seed_summary(inserted, skipped=total - inserted)
        _logger.info("seed completed", extra=summary)
        portfolio = seed_portfolio(session)
    _logger.info("seed portfolio completed", extra=portfolio.payload())
    return {**summary, **portfolio.payload()}


if __name__ == "__main__":  # pragma: no cover - module entry point
    run()
