"""`src/config/rule_loader.py` — Decimal parsing, schema validation and lock verification."""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from src.config.rule_loader import (
    POLICY_RULES_ROOT,
    PublishedRuleFileTamperedError,
    RuleFileValidationError,
    discover_rule_files,
    load_published_lock,
    load_rule_file,
    parse_rule_file,
    read_rule_document,
    sha256_of_file,
    verify_published_lock,
)
from src.types.enums import ProductCode, RuleSetStatus
from src.types.errors import NotFoundError, ValidationError


def _copy_rules(tmp_path: Path) -> Path:
    """Copy the real rule tree into ``tmp_path`` so a test can tamper with it safely."""
    root = tmp_path / "policy_rules"
    shutil.copytree(POLICY_RULES_ROOT, root)
    return root


def test_load_rule_file_returns_frozen_rule_set() -> None:
    rule_set = load_rule_file(ProductCode.MOTOR, 1)
    assert rule_set.product is ProductCode.MOTOR
    assert rule_set.version == 1
    assert rule_set.status is RuleSetStatus.PUBLISHED
    with pytest.raises((AttributeError, TypeError)):
        rule_set.version = 2  # type: ignore[misc]


def test_money_and_rates_are_decimal_never_float() -> None:
    premium = load_rule_file(ProductCode.MOTOR, 1).premium
    assert isinstance(premium.base_rate, Decimal)
    assert premium.base_rate == Decimal("0.0310")
    assert isinstance(premium.minimum_premium, Decimal)
    for rate_map in premium.rate_maps.values():
        assert all(isinstance(value, Decimal) for value in rate_map.values())
    for band_table in premium.bands.values():
        assert all(isinstance(band.multiplier, Decimal) for band in band_table)


def test_json_numbers_are_parsed_as_decimal(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text('{"rate": 0.1}', encoding="utf-8")
    document = read_rule_document(path, as_decimal=True)
    assert document["rate"] == Decimal("0.1")
    assert not isinstance(document["rate"], float)


def test_unknown_product_version_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        load_rule_file(ProductCode.MOTOR, 99)
    assert "v99" in str(excinfo.value)
    with pytest.raises(NotFoundError):
        load_rule_file(ProductCode.HOUSEHOLD, 1, rules_root=tmp_path)


def test_schema_invalid_file_raises_validation_error(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    path = root / "motor" / "v1.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    del body["premium"]["base_rate"]
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(RuleFileValidationError) as excinfo:
        load_rule_file(ProductCode.MOTOR, 1, rules_root=root)
    assert isinstance(excinfo.value, ValidationError)
    assert "premium" in str(excinfo.value)
    assert excinfo.value.details


def test_money_as_json_number_is_rejected(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    path = root / "motor" / "v1.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["premium"]["base_rate"] = 0.031
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(RuleFileValidationError):
        load_rule_file(ProductCode.MOTOR, 1, rules_root=root)


def test_parse_rule_file_accepts_a_direct_path() -> None:
    rule_set = parse_rule_file(POLICY_RULES_ROOT / "term_life" / "v1.json")
    assert rule_set.product is ProductCode.TERM_LIFE


def test_discover_rule_files_finds_the_three_v1_files() -> None:
    found = discover_rule_files()
    assert {(ref.product, ref.version) for ref in found} == {
        (ProductCode.TERM_LIFE, 1),
        (ProductCode.MOTOR, 1),
        (ProductCode.HOUSEHOLD, 1),
    }
    assert all(ref.status is RuleSetStatus.PUBLISHED for ref in found)
    assert all(len(ref.sha256) == 64 for ref in found)


def test_load_published_lock_matches_the_three_files() -> None:
    lock = load_published_lock()
    assert set(lock) == {"term_life/v1.json", "motor/v1.json", "household/v1.json"}
    for relative, digest in lock.items():
        assert sha256_of_file(POLICY_RULES_ROOT / relative) == digest


def test_verify_published_lock_passes_on_the_real_tree() -> None:
    verify_published_lock()


def test_verify_published_lock_fails_on_tampering(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    path = root / "household" / "v1.json"
    path.write_text(
        path.read_text(encoding="utf-8").replace("1500.00", "1500.01"), encoding="utf-8"
    )
    with pytest.raises(PublishedRuleFileTamperedError) as excinfo:
        verify_published_lock(rules_root=root)
    assert "household/v1.json" in str(excinfo.value)


def test_verify_published_lock_fails_when_a_listed_file_is_missing(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    (root / "motor" / "v1.json").unlink()
    with pytest.raises(PublishedRuleFileTamperedError) as excinfo:
        verify_published_lock(rules_root=root)
    assert "motor/v1.json" in str(excinfo.value)


def test_verify_published_lock_fails_when_a_published_file_is_unlisted(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    lock = root / "PUBLISHED.lock"
    kept = [
        line
        for line in lock.read_text(encoding="utf-8").splitlines()
        if "motor/v1.json" not in line
    ]
    lock.write_text("\n".join(kept) + "\n", encoding="utf-8")
    with pytest.raises(PublishedRuleFileTamperedError):
        verify_published_lock(rules_root=root)


def test_invalid_json_raises_rule_file_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuleFileValidationError):
        read_rule_document(path)


def test_non_object_json_raises_rule_file_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "array.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(RuleFileValidationError):
        read_rule_document(path)


def test_parse_rule_file_rejects_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        parse_rule_file(tmp_path / "nope.json")


def test_schema_valid_but_unparsable_document_is_a_validation_error(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    path = root / "motor" / "v1.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["effective_from"] = "2026-13-45"
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(RuleFileValidationError) as excinfo:
        load_rule_file(ProductCode.MOTOR, 1, rules_root=root)
    assert "rule set" in str(excinfo.value) or "schema" in str(excinfo.value)


def test_missing_lock_file_raises_not_found(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    (root / "PUBLISHED.lock").unlink()
    with pytest.raises(NotFoundError):
        load_published_lock(rules_root=root)


def test_malformed_lock_line_is_rejected(tmp_path: Path) -> None:
    root = _copy_rules(tmp_path)
    (root / "PUBLISHED.lock").write_text("deadbeef\n", encoding="utf-8")
    with pytest.raises(PublishedRuleFileTamperedError):
        load_published_lock(rules_root=root)
