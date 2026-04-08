from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[4]


def load_script_directory() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def get_head_revisions() -> tuple[str, ...]:
    return tuple(load_script_directory().get_heads())


def list_schema_revisions() -> tuple[str, ...]:
    script = load_script_directory()
    heads = tuple(script.get_heads())
    if len(heads) != 1:
        raise RuntimeError(f"Expected a single active Alembic head, got {heads!r}")

    ordered = [revision.revision for revision in script.walk_revisions(base="base", head=heads[0])]
    ordered.reverse()
    return tuple(ordered)


def get_current_schema_revision(session: Session) -> str | None:
    exists = session.execute(
        text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'")
    ).fetchone()
    if exists is None:
        return None

    row = session.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
    return None if row is None else str(row[0])


def revision_is_reachable(schema_revision: str, current_revision: str | None) -> bool:
    if current_revision is None:
        return False

    revisions = list_schema_revisions()
    try:
        return revisions.index(schema_revision) <= revisions.index(current_revision)
    except ValueError:
        return False
