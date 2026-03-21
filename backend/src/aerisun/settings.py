from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AERISUN_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Aerisun API"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    store_dir: Path = BACKEND_ROOT / ".store"
    data_dir: Path = BACKEND_ROOT / ".store"
    media_dir: Path = BACKEND_ROOT / ".store" / "media"
    secrets_dir: Path = BACKEND_ROOT / ".store" / "secrets"
    db_path: Path = BACKEND_ROOT / ".store" / "aerisun.db"
    litestream_config_path: Path = BACKEND_ROOT / "litestream.yml"
    litestream_replica_url: str = Field(
        default="sftp://backup-user@backup-host:22/backup/aerisun/aerisun.db"
    )
    backup_rsync_uri: str = Field(
        default="backup-user@backup-host:/backup/aerisun"
    )
    backup_ssh_port: int = 22
    backup_ssh_key: str | None = None
    sqlite_busy_timeout_ms: int = 5000
    seed_reference_data: bool = True
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    session_ttl_hours: int = 24

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.db_path.expanduser().resolve()}"

    def ensure_directories(self) -> None:
        self.store_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
        self.media_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
        self.secrets_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
        self.db_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
