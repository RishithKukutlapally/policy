"""Append-only repository for ``rule_set_versions`` (DEC-013, NFR-02).

Public surface: ``add`` plus three reads — ``latest_status``, ``list_for_product`` and
``active_for_product``. There is no update and no delete: a DRAFT replacement or a publish is a
new row with ``revision + 1``. The session belongs to the calling service, which owns the
transaction; this repository never commits.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.repository.models import RuleSetVersion
from src.types.enums import ProductCode, RuleSetStatus


class RuleSetVersionRepository:
    """Reads and appends rule-set version rows; it has no mutating operation by design."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        product: ProductCode,
        version: int,
        status: RuleSetStatus,
        content: Mapping[str, Any],
        content_sha256: str,
        actor_id: str,
        effective_from: date | None = None,
    ) -> RuleSetVersion:
        """Append the next ``revision`` of ``(product, version)`` and flush it."""
        row = RuleSetVersion(
            product=ProductCode(product).value,
            version=int(version),
            revision=self._next_revision(product, version),
            status=RuleSetStatus(status).value,
            effective_from=effective_from or date.fromisoformat(str(content["effective_from"])),
            content=dict(content),
            content_sha256=content_sha256,
            actor_id=actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def latest_status(self, product: ProductCode, version: int) -> RuleSetStatus | None:
        """Status of the highest-``revision`` row, or ``None`` when the version has no row."""
        row = self._latest_row(product, version)
        return None if row is None else RuleSetStatus(row.status)

    def list_for_product(self, product: ProductCode) -> list[RuleSetVersion]:
        """Every row of one product, oldest first (``version`` then ``revision``)."""
        statement = (
            select(RuleSetVersion)
            .where(RuleSetVersion.product == ProductCode(product).value)
            .order_by(RuleSetVersion.version.asc(), RuleSetVersion.revision.asc())
        )
        return list(self._session.execute(statement).scalars())

    def active_for_product(self, product: ProductCode) -> RuleSetVersion | None:
        """Highest ``version`` whose latest row is PUBLISHED, or ``None`` (AC-02, DEC-013)."""
        candidates = [
            row
            for row in self.list_for_product(product)
            if row.revision == self._max_revision(product, row.version)
            and row.status == RuleSetStatus.PUBLISHED.value
        ]
        return max(candidates, key=lambda row: row.version, default=None)

    def _latest_row(self, product: ProductCode, version: int) -> RuleSetVersion | None:
        """The highest-``revision`` row of ``(product, version)``."""
        statement = (
            select(RuleSetVersion)
            .where(
                RuleSetVersion.product == ProductCode(product).value,
                RuleSetVersion.version == int(version),
            )
            .order_by(RuleSetVersion.revision.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalars().first()

    def _max_revision(self, product: ProductCode, version: int) -> int:
        """Highest stored ``revision`` of ``(product, version)``; ``0`` when there is none."""
        statement = select(func.max(RuleSetVersion.revision)).where(
            RuleSetVersion.product == ProductCode(product).value,
            RuleSetVersion.version == int(version),
        )
        return int(self._session.execute(statement).scalar() or 0)

    def _next_revision(self, product: ProductCode, version: int) -> int:
        """Revision number for the row about to be appended (1 for the first)."""
        return self._max_revision(product, version) + 1
