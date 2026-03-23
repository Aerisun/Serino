"""Database preflight check for development environments.

Detects schema drift (DB version from another branch) and seed data
changes, so ``bootstrap.sh`` can decide whether to recreate the
database or force a reseed before starting the server.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("aerisun.db_preflight")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def get_known_revisions(alembic_versions_dir: Path) -> set[str]:
    """Collect all Alembic revision IDs present in the current branch."""
    revisions: set[str] = set()
    for py_file in alembic_versions_dir.glob("*.py"):
        for line in py_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("revision") and "=" in stripped:
                # e.g.  revision = "abc123def456"
                _, _, value = stripped.partition("=")
                rev = value.strip().strip("\"'")
                if rev:
                    revisions.add(rev)
    return revisions


def get_db_revision(db_path: Path) -> str | None:
    """Read the current Alembic revision from an existing SQLite DB."""
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "alembic_version" not in tables:
            return None
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def compute_seed_fingerprint(seed_py_path: Path) -> str:
    """SHA-256 hash (first 16 hex chars) of the seed module file."""
    content = seed_py_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def get_stored_seed_fingerprint(db_path: Path) -> str | None:
    """Read the seed fingerprint from ``_aerisun_meta`` (if it exists)."""
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "_aerisun_meta" not in tables:
            return None
        row = conn.execute("SELECT value FROM _aerisun_meta WHERE key='seed_fingerprint'").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def store_seed_fingerprint(db_path: Path, fingerprint: str) -> None:
    """Persist the seed fingerprint into ``_aerisun_meta``."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS _aerisun_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT OR REPLACE INTO _aerisun_meta (key, value) VALUES ('seed_fingerprint', ?)",
            (fingerprint,),
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------
# Main preflight entry point
# ------------------------------------------------------------------


def run_preflight(
    db_path: Path,
    alembic_dir: Path,
    seed_path: Path,
) -> dict[str, object]:
    """Check DB compatibility with the current branch.

    Returns
    -------
    dict with keys:
        action   – ``"ok"`` or ``"recreate"``
        reseed   – ``True`` if seed data should be refreshed
        reason   – human-readable explanation
    """
    known = get_known_revisions(alembic_dir / "versions")
    current_rev = get_db_revision(db_path)
    seed_fp = compute_seed_fingerprint(seed_path)
    stored_fp = get_stored_seed_fingerprint(db_path)

    # Case 1: no database yet
    if current_rev is None:
        logger.info("No existing database; will create fresh.")
        return {"action": "ok", "reseed": True, "reason": "fresh database"}

    # Case 2: DB revision matches current branch
    if current_rev in known:
        reseed = stored_fp != seed_fp
        if reseed:
            logger.info(
                "Seed definition changed (%s → %s); will reseed.",
                stored_fp,
                seed_fp,
            )
        return {"action": "ok", "reseed": reseed, "reason": "revision compatible"}

    # Case 3: DB revision not in current branch – delete and recreate
    logger.warning(
        "DB at revision '%s' not found in current branch migrations %s. Deleting database to recreate.",
        current_rev,
        sorted(known),
    )
    db_path.unlink()
    for suffix in ("-wal", "-shm"):
        wal = Path(str(db_path) + suffix)
        if wal.exists():
            wal.unlink()

    return {"action": "recreate", "reseed": True, "reason": f"revision '{current_rev}' not in branch"}
