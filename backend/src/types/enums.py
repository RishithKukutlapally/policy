"""Canonical PolicyForge enumerations (`docs/conventions.md`).

Pure standard library: `src.types` may not import any framework, logger or I/O.
"""

from __future__ import annotations

from enum import StrEnum


class ProductCode(StrEnum):
    """Insurable products in the catalog (AC-02)."""

    TERM_LIFE = "TERM_LIFE"
    MOTOR = "MOTOR"
    HOUSEHOLD = "HOUSEHOLD"


class PolicyStatus(StrEnum):
    """Policy lifecycle states; LAPSED, CANCELLED and RENEWED are terminal (AC-10)."""

    ACTIVE = "ACTIVE"
    ENDORSED = "ENDORSED"
    LAPSED = "LAPSED"
    CANCELLED = "CANCELLED"
    RENEWED = "RENEWED"


class ApplicationStatus(StrEnum):
    """Application workflow states from submission to issuance (AC-03, AC-04)."""

    SUBMITTED = "SUBMITTED"
    UNDERWRITING = "UNDERWRITING"
    AUTO_BIND = "AUTO_BIND"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DECLINED = "DECLINED"
    ISSUED = "ISSUED"


class Decision(StrEnum):
    """Stored underwriting outcome (AC-04)."""

    AUTO_BIND = "AUTO_BIND"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DECLINE = "DECLINE"


class UnderwriterDecision(StrEnum):
    """Request value sent by an underwriter; maps onto `Decision`."""

    APPROVE = "APPROVE"
    DECLINE = "DECLINE"


class EndorsementType(StrEnum):
    """Mid-term policy changes (AC-06, AC-16)."""

    CHANGE_ADDRESS = "CHANGE_ADDRESS"
    ADD_NOMINEE = "ADD_NOMINEE"
    CHANGE_SUM_INSURED = "CHANGE_SUM_INSURED"


class ActorRole(StrEnum):
    """Authenticated actor roles. SYSTEM is internal-only (DEC-010) and is never
    accepted from the `X-Actor-Role` header."""

    CUSTOMER = "CUSTOMER"
    UNDERWRITER = "UNDERWRITER"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


class RefundType(StrEnum):
    """Cancellation refund basis (AC-08)."""

    FREE_LOOK = "FREE_LOOK"
    PRO_RATA = "PRO_RATA"


class EndOfDayAction(StrEnum):
    """Result of `renewal_rules.renewal_action` for one policy (AC-07, AC-18)."""

    NONE = "NONE"
    RENEW = "RENEW"
    IN_GRACE = "IN_GRACE"
    LAPSE = "LAPSE"


class RuleSetStatus(StrEnum):
    """Lifecycle of a versioned rule set (AC-11)."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
