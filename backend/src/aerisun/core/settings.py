from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Use absolute path WITHOUT resolving symlinks so each git worktree gets its
# own .store/ directory instead of sharing the main branch's.
BACKEND_ROOT = Path(__file__).absolute().parents[3]
PROJECT_ROOT = BACKEND_ROOT.parent
PRODUCTION_STORE_ROOT = Path("/srv/aerisun/store")


def _resolve_env_files() -> tuple[Path, ...]:
    """Build the env-file loading chain (later overrides earlier).

    Order: .env → .env.{env} → .env.{env}.local
    """
    env = os.environ.get("AERISUN_ENVIRONMENT", "development")
    files: list[Path] = [PROJECT_ROOT / ".env"]
    for name in (f".env.{env}", f".env.{env}.local"):
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
    workflow_db_path: Path = PROJECT_ROOT / ".store" / "langgraph.db"
    api_base_path: str = "/api"
    admin_base_path: str = "/admin/"
    waline_base_path: str = "/waline"
    healthcheck_path: str = "/api/v1/site/readyz"
    frontend_dist_dir: Path = Path("/srv/aerisun/frontend")
    admin_dist_dir: Path = Path("/srv/aerisun/admin")
    site_url: str = "http://localhost:5173"
    waline_server_url: str = "/waline"
    release_version: str = ""
    backup_sync_tmp_dir: Path = PROJECT_ROOT / ".store" / ".backup-sync-tmp"
    backup_sync_default_site_slug: str = "aerisun"
    backup_sync_default_interval_minutes: int = 60
    backup_sync_chunk_size_bytes: int = 8 * 1024 * 1024
    sqlite_busy_timeout_ms: int = 5000
    seed_reference_data: bool = True
    seed_dev_data: bool = False
    seed_profile: str = "seed"
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())
    session_ttl_hours: int = 24
    public_session_ttl_hours: int = 24 * 30
    public_session_cookie_name: str = "aerisun_site_session"
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_state_secret: str = ""

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

    # Content subscriptions / newsletter
    subscription_dispatch_interval_minutes: int = 15
    subscription_smtp_auth_mode: str = "password"
    subscription_smtp_host: str = ""
    subscription_smtp_port: int = 587
    subscription_smtp_username: str = ""
    subscription_smtp_password: str = ""
    subscription_smtp_oauth_tenant: str = "common"
    subscription_smtp_oauth_client_id: str = ""
    subscription_smtp_oauth_client_secret: str = ""
    subscription_smtp_oauth_refresh_token: str = ""
    subscription_smtp_from_email: str = ""
    subscription_smtp_from_name: str = ""
    subscription_smtp_reply_to: str = ""
    subscription_smtp_use_tls: bool = True
    subscription_smtp_use_ssl: bool = False

    # Development-only seed overrides (from .env.development.local)
    dev_seed_subscription_enabled: bool = False
    dev_seed_agent_model_enabled: bool = False
    dev_seed_agent_model_provider: str = "openai_compatible"
    dev_seed_agent_model_base_url: str = ""
    dev_seed_agent_model: str = ""
    dev_seed_agent_model_api_key: str = ""
    dev_seed_agent_model_temperature: float = 0.2
    dev_seed_agent_model_timeout_seconds: int = 60
    dev_seed_agent_model_advisory_prompt: str = ""
    dev_seed_webhook_name: str = ""
    dev_seed_webhook_target_url: str = ""
    dev_seed_webhook_secret: str = ""
    dev_seed_webhook_event_types: str = ""
    dev_seed_webhook_headers_json: str = ""
    dev_seed_webhook_timeout_seconds: int = 10
    dev_seed_webhook_max_attempts: int = 6
    dev_seed_webhook_status: str = "active"

    # Logging
    log_level: str = "INFO"
    log_format: str = "auto"

    # Sentry
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    @model_validator(mode="after")
    def _normalize_runtime_paths(self) -> Settings:
        legacy_store_dir = (PROJECT_ROOT / ".store").expanduser()
        store_dir = self.store_dir.expanduser()

        if self.environment == "production" and store_dir == legacy_store_dir:
            self.store_dir = PRODUCTION_STORE_ROOT
            store_dir = self.store_dir

        def under_store(path: Path, *parts: str) -> Path:
            candidate = path.expanduser()
            if candidate == legacy_store_dir.joinpath(*parts):
                return store_dir.joinpath(*parts)
            return candidate

        self.data_dir = under_store(self.data_dir)
        self.media_dir = under_store(self.media_dir, "media")
        self.secrets_dir = under_store(self.secrets_dir, "secrets")
        self.db_path = under_store(self.db_path, "aerisun.db")
        self.waline_db_path = under_store(self.waline_db_path, "waline.db")
        self.workflow_db_path = under_store(self.workflow_db_path, "langgraph.db")
        self.backup_sync_tmp_dir = under_store(self.backup_sync_tmp_dir, ".backup-sync-tmp")
        return self

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
        self.backup_sync_tmp_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
        self.db_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.waline_db_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.workflow_db_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
