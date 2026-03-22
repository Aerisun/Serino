from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    store_dir = tmp_path / "store"
    data_dir = store_dir
    media_dir = store_dir / "media"
    secrets_dir = store_dir / "secrets"
    db_path = store_dir / "aerisun.db"
    waline_db_path = store_dir / "waline.db"

    monkeypatch.setenv("AERISUN_STORE_DIR", str(store_dir))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(secrets_dir))
    monkeypatch.setenv("AERISUN_DB_PATH", str(db_path))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(waline_db_path))
    monkeypatch.setenv("AERISUN_SEED_REFERENCE_DATA", "true")

    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.settings import get_settings

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
