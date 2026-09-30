"""SQLAlchemy 2 declarative models (`docs/conventions.md` -> "Persistence").

Money columns are ``Numeric(12, 2)`` and rates ``Numeric(9, 6)`` mapped to :class:`~decimal.Decimal`
— never ``Float`` (NFR-01). Append-only tables are documented as such and their repositories
expose ``add(...)`` plus reads only (NFR-02).

Split by bounded concern; importing this package registers every model on
:class:`src.repository.database.Base` so Alembic autogenerate and string-based foreign keys
resolve exactly as they did when all models lived in a single module.
"""

from __future__ import annotations

from src.repository.models._common import _in_clause, _new_uuid, _now
from src.repository.models.audit import (
    AUDIT_RECORDS_TABLE,
    AuditAction,
    AuditEntityType,
    AuditRecord,
)
from src.repository.models.lifecycle import (
    ENDORSEMENTS_TABLE,
    POLICY_STATE_TRANSITIONS_TABLE,
    PREMIUM_PAYMENTS_TABLE,
    REFUNDS_TABLE,
    Endorsement,
    PolicyStateTransition,
    PremiumPayment,
    Refund,
)
from src.repository.models.policies import POLICIES_TABLE, Policy
from src.repository.models.quotes import QUOTES_TABLE, Quote
from src.repository.models.rules import RULE_SET_VERSIONS_TABLE, RuleSetVersion
from src.repository.models.underwriting import (
    Application,
    UnderwritingDecision,
    UnderwritingOverride,
)

__all__ = [
    "AUDIT_RECORDS_TABLE",
    "ENDORSEMENTS_TABLE",
    "POLICIES_TABLE",
    "POLICY_STATE_TRANSITIONS_TABLE",
    "PREMIUM_PAYMENTS_TABLE",
    "QUOTES_TABLE",
    "REFUNDS_TABLE",
    "RULE_SET_VERSIONS_TABLE",
    "Application",
    "AuditAction",
    "AuditEntityType",
    "AuditRecord",
    "Endorsement",
    "Policy",
    "PolicyStateTransition",
    "PremiumPayment",
    "Quote",
    "Refund",
    "RuleSetVersion",
    "UnderwritingDecision",
    "UnderwritingOverride",
    "_in_clause",
    "_new_uuid",
    "_now",
]
