"""Alembic environment — URL from Settings, metadata from the declarative Base."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from src.config.settings import get_settings
from src.repository.database import Base, create_app_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Prefer an explicit ``-x url=...`` / ini URL, otherwise the configured settings URL."""
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to the script output without a DBAPI connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    engine = create_app_engine(_database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
    _ = pool  # imported for parity with the Alembic template


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
