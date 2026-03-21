from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from aerisun.models import Base
from aerisun.settings import Settings, get_settings


@lru_cache(maxsize=1)
def get_engine() -> object:
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


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())

