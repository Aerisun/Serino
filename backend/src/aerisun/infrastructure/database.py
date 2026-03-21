"""Legacy compatibility wrappers for the original infrastructure import path."""

from __future__ import annotations

from aerisun.db import get_engine, get_session as get_db_session, get_session_factory, init_db


def initialize_database() -> None:
    init_db()


__all__ = [
    "get_db_session",
    "get_engine",
    "get_session_factory",
    "initialize_database",
]
