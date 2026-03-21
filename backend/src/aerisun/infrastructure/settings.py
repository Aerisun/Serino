from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "Aerisun API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./.data/aerisun.db"
    sqlite_busy_timeout: Annotated[int, Field(ge=0)] = 5000
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True
    log_level: str = "info"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

