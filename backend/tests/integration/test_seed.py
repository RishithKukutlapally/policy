"""Integration tests: the idempotent, tamper-checked seed import (AC-02, NFR-05)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.rule_loader import POLICY_RULES_ROOT, PublishedRuleFileTamperedError
from src.repository.database import Base, create_app_engine
from src.repository.models import RuleSetVersion
from src.seed import import_published_rule_files, seed_summary

pytestmark = pytest.mark.integration


@pytest.fixture(name="session")
def _session() -> Iterator[Session]:
    engine = create_app_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _count(session: Session) -> int:
    return session.execute(select(func.count()).select_from(RuleSetVersion)).scalar_one()


def test_seed_inserts_three_rows(session: Session) -> None:
    assert import_published_rule_files(session) == 3
    session.commit()
    assert _count(session) == 3


def test_seed_is_idempotent(session: Session) -> None:
    import_published_rule_files(session)
    session.commit()
    assert import_published_rule_files(session) == 0
    session.commit()
    assert _count(session) == 3


def test_seed_hashes_match_the_published_lock(session: Session) -> None:
    import_published_rule_files(session)
    session.commit()
    lock = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in (POLICY_RULES_ROOT / "PUBLISHED.lock").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    folders = {"TERM_LIFE": "term_life", "MOTOR": "motor", "HOUSEHOLD": "household"}
    for row in session.execute(select(RuleSetVersion)).scalars():
        assert row.content_sha256 == lock[f"{folders[row.product]}/v{row.version}.json"]


def test_seed_aborts_and_inserts_nothing_when_a_file_is_tampered(
    session: Session, tmp_path: Path
) -> None:
    root = tmp_path / "policy_rules"
    shutil.copytree(POLICY_RULES_ROOT, root)
    target = root / "household" / "v1.json"
    target.write_text(
        target.read_text(encoding="utf-8").replace("1500.00", "1500.01"), encoding="utf-8"
    )
    with pytest.raises(PublishedRuleFileTamperedError) as excinfo:
        import_published_rule_files(session, rules_root=root)
    assert "household/v1.json" in str(excinfo.value)
    session.rollback()
    assert _count(session) == 0


def test_seed_summary_is_a_json_safe_mapping(session: Session) -> None:
    inserted = import_published_rule_files(session)
    summary = seed_summary(inserted, skipped=3 - inserted)
    assert summary["inserted"] == inserted
    assert summary["event"] == "seed_completed"
