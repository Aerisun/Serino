from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Use absolute path WITHOUT resolving symlinks so each git worktree gets its own .store/ directory instead of sharing the main branch's.
BACKEND_ROOT = Path(__file__).absolute().parents[3]
PROJECT_ROOT = BACKEND_ROOT.parent


def _resolve_env_files() -> tuple[Path, ...]:
    """Build the env-file loading chain (later overrides earlier).

    Order: .env → .env.{env} → .env.local → .env.{env}.local
    Mirrors Vite's native ``loadEnv`` resolution.
    """
    env = os.environ.get("AERISUN_ENVIRONMENT", "development")
    files: list[Path] = [PROJECT_ROOT / ".env"]
    for name in (f".env.{env}", ".env.local", f".env.{env}.local"):
        p = PROJECT_ROOT / name
        if p.exists():
            files.append(p)
    return tuple(files)


DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://[::1]:3000",
    "http://[::1]:3001",
    "http://[::1]:5173",
    "http://[::1]:8080",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AERISUN_",
        env_file=_resolve_env_files(),
        extra="ignore",
    )

    app_name: str = "Aerisun API"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    store_dir: Path = PROJECT_ROOT / ".store"
    data_dir: Path = PROJECT_ROOT / ".store"
    media_dir: Path = PROJECT_ROOT / ".store" / "media"
    secrets_dir: Path = PROJECT_ROOT / ".store" / "secrets"
    db_path: Path = PROJECT_ROOT / ".store" / "aerisun.db"
    waline_db_path: Path = PROJECT_ROOT / ".store" / "waline.db"
    site_url: str = "http://localhost:5173"
    waline_server_url: str = "http://localhost:8360"
    litestream_config_path: Path = BACKEND_ROOT / "litestream.yml"
    litestream_replica_url: str = Field(default="sftp://backup-user@backup-host:22/backup/aerisun/aerisun.db")
    waline_litestream_replica_url: str = Field(default="sftp://backup-user@backup-host:22/backup/aerisun/waline.db")
    backup_rsync_uri: str = Field(default="backup-user@backup-host:/backup/aerisun")
    backup_ssh_port: int = 22
    backup_ssh_key: str | None = None
    sqlite_busy_timeout_ms: int = 5000
    seed_reference_data: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())
    session_ttl_hours: int = 24

    # Feed crawling
    feed_crawl_enabled: bool = True
    feed_crawl_interval_hours: int = 6
    feed_crawl_timeout_connect: int = 10
    feed_crawl_timeout_read: int = 15
    feed_crawl_max_items_per_source: int = 20
    feed_crawl_user_agent: str = (
        "Mozilla/5.0 (compatible; Aerisun/1.0; FriendCircle RSS Reader; +https://github.com/Aerisun)"
    )

    # Logging
    log_level: str = "INFO"
    log_format: str = "auto"

    # Sentry
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.db_path.expanduser().resolve()}"

    _LOCALHOST_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")

    def has_only_localhost_origins(self) -> bool:
        return all(self._LOCALHOST_RE.match(o) for o in self.cors_origins)

    def ensure_directories(self) -> None:
        self.store_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
        self.media_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
        self.secrets_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
        self.db_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.waline_db_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
