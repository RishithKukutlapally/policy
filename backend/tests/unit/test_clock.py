"""Unit tests for src.lib.clock (DEC-012 business date)."""

from __future__ import annotations

import datetime as dt

import pytest

from src.lib import clock


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLICYFORGE_BUSINESS_DATE", raising=False)
    monkeypatch.delenv("BUSINESS_DATE", raising=False)


def test_today_returns_real_today_when_unset() -> None:
    assert clock.today() == dt.date.today()


def test_today_honours_business_date_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "2026-10-01")
    assert clock.today() == dt.date(2026, 10, 1)


def test_today_honours_unprefixed_business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUSINESS_DATE", "2027-01-15")
    assert clock.today() == dt.date(2027, 1, 15)


def test_blank_business_date_falls_back_to_real_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "   ")
    assert clock.today() == dt.date.today()


def test_invalid_business_date_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "not-a-date")
    with pytest.raises(ValueError, match="POLICYFORGE_BUSINESS_DATE"):
        clock.today()


def test_now_utc_is_timezone_aware() -> None:
    assert clock.now_utc().tzinfo is dt.UTC


def test_now_utc_uses_business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "2026-10-01")
    assert clock.now_utc().date() == dt.date(2026, 10, 1)
