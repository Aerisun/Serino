from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from aerisun.infrastructure.settings import get_settings
from aerisun.shared.base import Base

# Import all models so their tables are registered on Base.metadata.
from aerisun.modules.site_config import models as site_config_models  # noqa: F401
from aerisun.modules.content import models as content_models  # noqa: F401
from aerisun.modules.engagement import models as engagement_models  # noqa: F401
from aerisun.modules.social import models as social_models  # noqa: F401
from aerisun.modules.media import models as media_models  # noqa: F401
from aerisun.modules.iam import models as iam_models  # noqa: F401
from aerisun.modules.ops import models as ops_models  # noqa: F401


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    _ensure_sqlite_directory(settings.database_url)
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout};")
        cursor.close()

    return engine


def _ensure_sqlite_directory(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return
    if not url.database:
        return
    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def initialize_database() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    from aerisun.infrastructure.seed import seed_database

    with SessionLocal() as session:
        seed_database(session)
        session.commit()
