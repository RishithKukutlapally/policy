"""Audit recording helper (NFR-03, NFR-04).

Thin wrapper over :class:`~src.repository.audit_repository.AuditRecordRepository` that stamps the
current correlation id and refuses any ``detail`` payload carrying PII. It is a *service*: the
caller owns the transaction and this helper never commits.

The ``detail`` guard has two halves, both applied at any nesting depth so a caller cannot slip
personal data past them by nesting one level down:

* **reject** — a key whose *name* looks like personal data is refused outright (``ValueError``);
* **mask** — every string *value* is passed through :func:`src.lib.logging.mask_pii`, so an
  Aadhaar- or PAN-shaped substring typed into an operator's free-text comment is stored in its
  masked form. ``audit_records`` is append-only (NFR-02), so this is the only chance to do it.
"""

from __future__ import annotations

import re
from typing import Any, Final

from sqlalchemy.orm import Session

from src.lib.correlation import get_correlation_id
from src.lib.logging import mask_pii
from src.repository.audit_repository import AuditRecordRepository
from src.repository.models import AuditAction, AuditEntityType, AuditRecord
from src.types.enums import ActorRole

#: Detail keys that could carry personal data; audit rows must never hold them (NFR-03).
_PII_KEY: Final = re.compile(
    r"aadh?aar|(^|_)pan(_|$)|health|medical|kyc|nominee|full_?name|date_?of_?birth|dob|address",
    re.IGNORECASE,
)


def _reject_pii(value: Any) -> None:
    """Raise when any key of ``value``, at any depth, looks like personal data."""
    if isinstance(value, dict):
        offenders = sorted(str(key) for key in value if _PII_KEY.search(str(key)))
        if offenders:
            raise ValueError(f"audit detail must not carry PII keys: {', '.join(offenders)}")
        for item in value.values():
            _reject_pii(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_pii(item)


def _mask_values(value: Any) -> Any:
    """Return ``value`` with every string, at any depth, run through :func:`mask_pii`."""
    if isinstance(value, dict):
        return {key: _mask_values(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_values(item) for item in value]
    if isinstance(value, str):
        return mask_pii(value)
    return value


def sanitise_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """Reject PII-named keys and mask PII-shaped strings anywhere inside ``detail`` (NFR-03)."""
    _reject_pii(detail)
    masked: dict[str, Any] = _mask_values(detail)
    return masked


class AuditService:
    """Records the audited actions listed in `docs/conventions.md` -> "Audit actions"."""

    def __init__(self, session: Session) -> None:
        self._records = AuditRecordRepository(session)

    def record(
        self,
        *,
        action: AuditAction,
        actor_id: str,
        actor_role: ActorRole,
        entity_type: AuditEntityType,
        entity_id: str,
        detail: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Append one audit row for ``action`` taken by ``actor_id`` on ``entity_id``."""
        safe_detail = sanitise_detail(detail) if detail else None
        return self._records.add(
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=safe_detail,
            correlation_id=get_correlation_id(),
        )

    def list_for_entity(self, entity_type: AuditEntityType, entity_id: str) -> list[AuditRecord]:
        """Return the audit trail of one entity, oldest first."""
        return self._records.list_for_entity(entity_type, entity_id)
