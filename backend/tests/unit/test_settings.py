"""Unit tests for src.config.settings."""

from __future__ import annotations

import pytest

from src.config.settings import Settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_URL",
        "API_PORT",
        "UI_PORT",
        "RENEWAL_WINDOW_DAYS",
        "BUSINESS_DATE",
        "POLICYFORGE_DATABASE_URL",
        "POLICYFORGE_API_PORT",
        "POLICYFORGE_UI_PORT",
        "POLICYFORGE_RENEWAL_WINDOW_DAYS",
        "POLICYFORGE_BUSINESS_DATE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_conventions() -> None:
    settings = Settings()
    assert settings.database_url == "sqlite:///./policyforge.db"
    assert settings.api_port == 8000
    assert settings.ui_port == 3000
    assert settings.renewal_window_days == 30
    assert settings.business_date is None


def test_database_url_override_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./tmp-test.db")
    assert Settings().database_url == "sqlite:///./tmp-test.db"


def test_prefixed_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICYFORGE_DATABASE_URL", "sqlite:///./prefixed.db")
    monkeypatch.setenv("POLICYFORGE_API_PORT", "8123")
    settings = Settings()
    assert settings.database_url == "sqlite:///./prefixed.db"
    assert settings.api_port == 8123


def test_business_date_parses_iso_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICYFORGE_BUSINESS_DATE", "2026-10-01")
    business_date = Settings().business_date
    assert business_date is not None
    assert business_date.isoformat() == "2026-10-01"


def test_get_settings_is_cached() -> None:
    from src.config.settings import get_settings

    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
