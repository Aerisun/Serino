from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from aerisun.core.base import Base
from aerisun.core.settings import get_settings
from aerisun.core.time import normalize_shanghai_datetime

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _adapt_sqlite_date(value: date) -> str:
    return value.isoformat()


def _adapt_sqlite_datetime(value: datetime) -> str:
    return normalize_shanghai_datetime(value).isoformat(sep=" ")


def _register_sqlite_adapters() -> None:
    # Python 3.12+ deprecates sqlite3's implicit datetime adapter. Registering
    # an explicit ISO-8601 adapter preserves current storage semantics and keeps
    # test output warning-free.
    sqlite3.register_adapter(date, _adapt_sqlite_date)
    sqlite3.register_adapter(datetime, _adapt_sqlite_datetime)


@lru_cache(maxsize=1)
def get_engine() -> object:
    _register_sqlite_adapters()
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        connect_args={
            "check_same_thread": False,
            "timeout": settings.sqlite_busy_timeout_ms / 1000,
        },
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms};")
        cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Dispose the SQLAlchemy engine and clear cached factories."""
    engine = get_engine()
    engine.dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def run_database_migrations() -> None:
    settings = get_settings()
    settings.ensure_directories()

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
