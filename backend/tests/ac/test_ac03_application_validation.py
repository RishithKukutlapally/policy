"""AC-03: application validation against the active rule set."""

from typing import Any

import pytest

from src.config.rule_loader import parse_rule_file, rule_file_path
from src.domain.application_validator import kyc_status, validate_application
from src.types.enums import ProductCode

KYC: dict[str, Any] = {
    "full_name": "Test Customer 01",
    "date_of_birth": "1996-04-01",
    "aadhaar": "999900000001",
    "pan": "AAAAA0001A",
    "address": "1 Sample Street, Testville",
}
MOTOR_RISK: dict[str, Any] = {
    "owner_age": 30,
    "sum_insured": "500000.00",
    "vehicle_age_years": 3,
    "engine_cc": 1200,
    "zone": "A",
    "ncb_percent": "20",
}
TL_RISK: dict[str, Any] = {
    "age": 35,
    "term_years": 20,
    "smoker": False,
    "sum_insured": "1000000.00",
}
HH_RISK: dict[str, Any] = {
    "proposer_age": 40,
    "construction_type": "BRICK",
    "in_flood_zone": False,
    "has_security_system": True,
    "sum_insured": "1000000.00",
}


def rs(product: ProductCode = ProductCode.MOTOR):  # type: ignore[no-untyped-def]
    return parse_rule_file(rule_file_path(product, 1))


@pytest.mark.ac("AC-03")
def test_ac03_valid_application_passes() -> None:
    """AC-03: valid applications for every product return no errors."""
    assert validate_application(rs(), KYC, MOTOR_RISK) == []
    assert kyc_status([]) == "VERIFIED"
    assert validate_application(rs(ProductCode.HOUSEHOLD), KYC, HH_RISK) == []
    health = {"has_pre_existing_condition": False, "details": "none"}
    assert validate_application(rs(ProductCode.TERM_LIFE), KYC, TL_RISK, health) == []


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize(
    ("kyc_patch", "field"),
    [
        ({"pan": "ABC123"}, "kyc.pan"),
        ({"aadhaar": "12345"}, "kyc.aadhaar"),
        ({"date_of_birth": "01-04-1996"}, "kyc.date_of_birth"),
    ],
)
def test_ac03_invalid_kyc_format(kyc_patch: dict[str, Any], field: str) -> None:
    """AC-03: malformed KYC values give INVALID_FORMAT on the exact field."""
    errors = validate_application(rs(), {**KYC, **kyc_patch}, MOTOR_RISK)
    assert errors == [(field, "INVALID_FORMAT")]
    assert kyc_status(errors) == "REJECTED"


@pytest.mark.ac("AC-03")
def test_ac03_missing_fields_required() -> None:
    """AC-03: missing KYC, risk and health fields are REQUIRED."""
    kyc = {k: v for k, v in KYC.items() if k != "full_name"}
    assert ("kyc.full_name", "REQUIRED") in validate_application(rs(), kyc, MOTOR_RISK)
    risk = {k: v for k, v in MOTOR_RISK.items() if k != "engine_cc"}
    assert ("engine_cc", "REQUIRED") in validate_application(rs(), KYC, risk)
    errors = validate_application(rs(ProductCode.TERM_LIFE), KYC, TL_RISK)
    assert errors == [("health_declaration", "REQUIRED")]


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"owner_age": 76}, "owner_age"),
        ({"owner_age": 17}, "owner_age"),
        ({"sum_insured": "5000000.01"}, "sum_insured"),
        ({"sum_insured": "99999.99"}, "sum_insured"),
    ],
)
def test_ac03_out_of_eligibility_range(patch: dict[str, Any], field: str) -> None:
    """AC-03: age or sum insured outside eligibility is OUT_OF_RANGE."""
    assert validate_application(rs(), KYC, {**MOTOR_RISK, **patch}) == [(field, "OUT_OF_RANGE")]


@pytest.mark.ac("AC-03")
def test_ac03_all_failures_reported_together_without_pii() -> None:
    """AC-03: every failing field is reported at once and no PII value leaks."""
    kyc = {**KYC, "aadhaar": "99990000000", "pan": "ZZZ999"}
    errors = validate_application(rs(), kyc, {**MOTOR_RISK, "owner_age": 99, "zone": "C"})
    assert {e.field for e in errors} == {"kyc.aadhaar", "kyc.pan", "owner_age", "zone"}
    rendered = repr(errors) + str(errors)
    assert "99990000000" not in rendered
    assert "ZZZ999" not in rendered
