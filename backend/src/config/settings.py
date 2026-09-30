"""Typed application settings (canonical list: docs/conventions.md -> Settings).

Every value is read from the environment. Each field accepts both the prefixed name
(``POLICYFORGE_DATABASE_URL``) and the bare name (``DATABASE_URL``), the prefixed one winning.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DATABASE_URL = "sqlite:" + "///./policyforge.db"


def _aliases(name: str) -> AliasChoices:
    """Accept ``POLICYFORGE_<NAME>`` first, then the bare ``<NAME>``."""
    upper = name.upper()
    return AliasChoices(f"POLICYFORGE_{upper}", upper)


class Settings(BaseSettings):
    """Runtime configuration for the PolicyForge API."""

    model_config = SettingsConfigDict(
        env_prefix="POLICYFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default=_DEFAULT_DATABASE_URL,
        validation_alias=_aliases("database_url"),
        description="SQLAlchemy database URL.",
    )
    api_port: int = Field(
        default=8000,
        validation_alias=_aliases("api_port"),
        description="Port the FastAPI application listens on.",
    )
    ui_port: int = Field(
        default=3000,
        validation_alias=_aliases("ui_port"),
        description="Port the Vite UI listens on.",
    )
    renewal_window_days: int = Field(
        default=30,
        validation_alias=_aliases("renewal_window_days"),
        description="Renewal opens this many days before the policy expiry date.",
    )
    business_date: dt.date | None = Field(
        default=None,
        validation_alias=_aliases("business_date"),
        description="DEC-012: overrides 'today' for the whole app; unset means the real today.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` instance."""
    return Settings()
