from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Use absolute path WITHOUT resolving symlinks so each git worktree gets its
# own .store/ directory instead of sharing the main branch's.
BACKEND_ROOT = Path(__file__).absolute().parents[3]
PROJECT_ROOT = BACKEND_ROOT.parent


@dataclass(frozen=True)
class ResolvedSecret:
    key: str
    filename: str
    path: Path
    value: str
    source: Literal["file", "env", "missing"]

    @property
    def configured(self) -> bool:
        return bool(self.value)

    def matches_any(self, *values: str) -> bool:
        return self.value in {item for item in values if item}


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
    api_base_path: str = "/api"
    admin_base_path: str = "/admin/"
    waline_base_path: str = "/waline"
    healthcheck_path: str = "/api/v1/site/healthz"
    frontend_dist_dir: Path = Path("/srv/aerisun/frontend")
    admin_dist_dir: Path = Path("/srv/aerisun/admin")
    site_url: str = "http://localhost:5173"
    waline_server_url: str = "/waline"
    litestream_config_path: Path = BACKEND_ROOT / "litestream.yml"
    litestream_replica_url: str = Field(default="sftp://backup-user@backup-host:22/backup/aerisun/aerisun.db")
    waline_litestream_replica_url: str = Field(default="sftp://backup-user@backup-host:22/backup/aerisun/waline.db")
    backup_rsync_uri: str = Field(default="backup-user@backup-host:/backup/aerisun")
    backup_ssh_port: int = 22
    backup_ssh_key: str | None = None
    sqlite_busy_timeout_ms: int = 5000
    seed_reference_data: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())

    # Emergency CORS escape hatch (non-development only).
    # Format: JSON array string, e.g. ["https://example.com", "https://admin.example.com"]
    production_cors_origins_override: list[str] | None = None

    session_ttl_hours: int = 24
    public_session_ttl_hours: int = 24 * 30
    public_session_cookie_name: str = "aerisun_site_session"
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""

    # IP geolocation
    ip_geo_enabled: bool = True
    ip_geo_api_base_url: str = "https://freeipapi.com/api/json"
    ip_geo_timeout_seconds: float = 3.0
    ip_geo_cache_ttl_seconds: int = 24 * 60 * 60

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

    # Sentry (migration fallback; prefer .store/secrets/sentry_dsn.txt)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.db_path.expanduser().resolve()}"

    _LOCALHOST_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")

    def _normalize_secret_value(self, value: str | None) -> str:
        return (value or "").strip()

    def _secret_path(self, filename: str) -> Path:
        return self.secrets_dir.expanduser() / filename

    def resolve_secret(
        self,
        *,
        key: str,
        filename: str,
        fallback_value: str = "",
        env_name: str | None = None,
    ) -> ResolvedSecret:
        path = self._secret_path(filename)
        file_value = ""
        try:
            if path.exists() and path.is_file():
                file_value = path.read_text(encoding="utf-8").strip()
        except OSError:
            file_value = ""
        if file_value:
            return ResolvedSecret(key=key, filename=filename, path=path, value=file_value, source="file")

        env_value = self._normalize_secret_value(os.environ.get(env_name)) if env_name else ""
        if env_value:
            return ResolvedSecret(key=key, filename=filename, path=path, value=env_value, source="env")

        fallback = self._normalize_secret_value(fallback_value)
        if fallback:
            return ResolvedSecret(key=key, filename=filename, path=path, value=fallback, source="env")

        return ResolvedSecret(key=key, filename=filename, path=path, value="", source="missing")

    def oauth_google_client_id_secret(self) -> ResolvedSecret:
        return self.resolve_secret(
            key="oauth_google_client_id",
            filename="oauth_google_client_id.txt",
            fallback_value=self.oauth_google_client_id,
        )

    def oauth_google_client_secret_secret(self) -> ResolvedSecret:
        return self.resolve_secret(
            key="oauth_google_client_secret",
            filename="oauth_google_client_secret.txt",
            fallback_value=self.oauth_google_client_secret,
        )

    def oauth_github_client_id_secret(self) -> ResolvedSecret:
        return self.resolve_secret(
            key="oauth_github_client_id",
            filename="oauth_github_client_id.txt",
            fallback_value=self.oauth_github_client_id,
        )

    def oauth_github_client_secret_secret(self) -> ResolvedSecret:
        return self.resolve_secret(
            key="oauth_github_client_secret",
            filename="oauth_github_client_secret.txt",
            fallback_value=self.oauth_github_client_secret,
        )

    def sentry_dsn_secret(self) -> ResolvedSecret:
        return self.resolve_secret(
            key="sentry_dsn",
            filename="sentry_dsn.txt",
            fallback_value=self.sentry_dsn,
        )

    def waline_jwt_secret(self) -> ResolvedSecret:
        return self.resolve_secret(
            key="waline_jwt_token",
            filename="waline_jwt_token.txt",
        )

    def oauth_provider_secrets(self, provider: str) -> tuple[ResolvedSecret, ResolvedSecret]:
        normalized = provider.strip().lower()
        if normalized == "google":
            return self.oauth_google_client_id_secret(), self.oauth_google_client_secret_secret()
        if normalized == "github":
            return self.oauth_github_client_id_secret(), self.oauth_github_client_secret_secret()
        raise ValueError(f"Unsupported oauth provider: {provider}")

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
