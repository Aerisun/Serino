from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    data_dir = tmp_path / "data"
    media_dir = tmp_path / "media"
    secrets_dir = tmp_path / "secrets"
    db_path = data_dir / "aerisun.db"

    monkeypatch.setenv("AERISUN_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(secrets_dir))
    monkeypatch.setenv("AERISUN_DB_PATH", str(db_path))
    monkeypatch.setenv("AERISUN_SEED_REFERENCE_DATA", "true")

    from aerisun.db import get_engine, get_session_factory
    from aerisun.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    from aerisun.main import app

    with TestClient(app) as test_client:
        yield test_client

    engine = get_engine()
    engine.dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
