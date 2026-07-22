import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from flipradar.core.settings import get_settings
from flipradar.database.base import Base
import flipradar.domain.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    return os.getenv("ALEMBIC_DATABASE_URL") or get_settings().database_url


def _sync_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def _is_async_url(url: str) -> bool:
    return "+asyncpg://" in url or "+aiosqlite://" in url


def _configure_url() -> str:
    url = _database_url()
    config.set_main_option("sqlalchemy.url", url)
    return url


def _include_object(
    object_,
    name: str | None,
    type_: str,
    reflected,
    compare_to,
) -> bool:
    del object_, reflected, compare_to
    if type_ == "table" and name == "alembic_version":
        return False
    return True


def _context_options(connection=None, url: str | None = None) -> dict:
    options = {
        "target_metadata": target_metadata,
        "include_object": _include_object,
        "compare_type": True,
        "compare_server_default": True,
        "render_as_batch": True,
    }
    if connection is not None:
        options["connection"] = connection
    if url is not None:
        options["url"] = url
        options["literal_binds"] = True
        options["dialect_opts"] = {"paramstyle": "named"}
    return options


def run_migrations_offline() -> None:
    url = _sync_database_url(_configure_url())
    context.configure(**_context_options(url=url))

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(**_context_options(connection=connection))

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    _configure_url()
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_sync_migrations() -> None:
    url = _sync_database_url(_configure_url())
    config.set_main_option("sqlalchemy.url", url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


def run_migrations_online() -> None:
    url = _configure_url()
    if _is_async_url(url):
        asyncio.run(run_async_migrations())
    else:
        run_sync_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
