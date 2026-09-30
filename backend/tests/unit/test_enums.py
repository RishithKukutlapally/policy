"""Canonical enum membership (AC-02, AC-10)."""

from __future__ import annotations

import pytest

from src.types.enums import (
    ActorRole,
    ApplicationStatus,
    Decision,
    EndOfDayAction,
    EndorsementType,
    PolicyStatus,
    ProductCode,
    RefundType,
    RuleSetStatus,
    UnderwriterDecision,
)

EXPECTED = {
    ProductCode: ["TERM_LIFE", "MOTOR", "HOUSEHOLD"],
    PolicyStatus: ["ACTIVE", "ENDORSED", "LAPSED", "CANCELLED", "RENEWED"],
    ApplicationStatus: [
        "SUBMITTED",
        "UNDERWRITING",
        "AUTO_BIND",
        "MANUAL_REVIEW",
        "DECLINED",
        "ISSUED",
    ],
    Decision: ["AUTO_BIND", "MANUAL_REVIEW", "DECLINE"],
    UnderwriterDecision: ["APPROVE", "DECLINE"],
    EndorsementType: ["CHANGE_ADDRESS", "ADD_NOMINEE", "CHANGE_SUM_INSURED"],
    ActorRole: ["CUSTOMER", "UNDERWRITER", "ADMIN", "SYSTEM"],
    RefundType: ["FREE_LOOK", "PRO_RATA"],
    EndOfDayAction: ["NONE", "RENEW", "IN_GRACE", "LAPSE"],
    RuleSetStatus: ["DRAFT", "PUBLISHED"],
}


@pytest.mark.ac("AC-02")
def test_ac02_product_code_has_exactly_three_products() -> None:
    assert [p.value for p in ProductCode] == ["TERM_LIFE", "MOTOR", "HOUSEHOLD"]


@pytest.mark.parametrize("enum_type", list(EXPECTED))
def test_enum_members_match_the_conventions(enum_type: type) -> None:
    assert [member.value for member in enum_type] == EXPECTED[enum_type]


@pytest.mark.parametrize("enum_type", list(EXPECTED))
def test_enum_members_are_plain_strings(enum_type: type) -> None:
    assert all(isinstance(member.value, str) for member in enum_type)


def test_system_role_exists_for_the_end_of_day_scheduler() -> None:
    assert ActorRole("SYSTEM") is ActorRole.SYSTEM


def test_unknown_member_raises_value_error() -> None:
    with pytest.raises(ValueError):
        ProductCode("TRAVEL")
