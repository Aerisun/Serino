"""开发环境数据库预检。

检测数据库版本漂移和种子数据变化，供 bootstrap.sh 判断是否重建数据库或重新灌种子。
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

from aerisun.core.seed_profile import normalize_seed_profile

logger = logging.getLogger("aerisun.db_preflight")


def _iter_seed_fingerprint_paths(seed_py_path: Path) -> list[Path]:
    paths = [seed_py_path]
    seed_steps_dir = seed_py_path.parent / "seed_steps"
    if seed_steps_dir.exists():
        paths.extend(sorted(seed_steps_dir.rglob("*.py")))
    return paths


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _has_legacy_dev_seed_residue(db_path: Path) -> bool:
    """Detect old dev-seed sample rows left behind in a DB labeled as production seed."""
    if not db_path.exists():
        return False

    conn = sqlite3.connect(str(db_path))
    try:
        if _table_exists(conn, "friend_feed_sources"):
            row = conn.execute(
                "SELECT 1 FROM friend_feed_sources WHERE feed_url = ? LIMIT 1",
                ("https://arthals.ink/rss.xml",),
            ).fetchone()
            if row is not None:
                return True

        if _table_exists(conn, "friends"):
            row = conn.execute(
                "SELECT 1 FROM friends WHERE name = ? LIMIT 1",
                ("Arthals' ink",),
            ).fetchone()
            if row is not None:
                return True

        if _table_exists(conn, "posts"):
            row = conn.execute(
                "SELECT 1 FROM posts WHERE slug IN (?, ?) LIMIT 1",
                ("from-zero-design-system", "liquid-glass-css-notes"),
            ).fetchone()
            if row is not None:
                return True
    finally:
        conn.close()

    return False


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def get_known_revisions(alembic_versions_dir: Path) -> set[str]:
    """收集当前分支里的 Alembic 迁移版本。"""
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
    """读取现有 SQLite 数据库的当前 Alembic 版本。"""
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


def compute_seed_fingerprint(seed_py_path: Path, *, seed_profile: str = "default") -> str:
    """计算 seed 文件的指纹，取 SHA-256 前 16 位。

    把 profile 一并纳入指纹，确保在 dev/dev-pseed 之间切换时能触发重灌。
    """
    digest = hashlib.sha256()
    digest.update(seed_profile.encode("utf-8"))
    digest.update(b"\0")
    for path in _iter_seed_fingerprint_paths(seed_py_path):
        digest.update(str(path.relative_to(seed_py_path.parent)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _get_meta_value(db_path: Path, key: str) -> str | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "_aerisun_meta" not in tables:
            return None
        row = conn.execute("SELECT value FROM _aerisun_meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_stored_seed_fingerprint(db_path: Path) -> str | None:
    """读取数据库里保存的种子指纹。"""
    return _get_meta_value(db_path, "seed_fingerprint")


def store_seed_metadata(db_path: Path, *, fingerprint: str) -> None:
    """把种子指纹写入 _aerisun_meta。"""
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
    *,
    seed_profile: str = "default",
) -> dict[str, object]:
    """检查数据库是否和当前分支兼容。

    返回值包含：
        action："ok" 或 "recreate"
        reseed：是否需要重新灌种子
        reason：原因说明
    """
    known = get_known_revisions(alembic_dir / "versions")
    current_rev = get_db_revision(db_path)
    normalized_profile = normalize_seed_profile(seed_profile)
    seed_fp = compute_seed_fingerprint(seed_path, seed_profile=normalized_profile)
    stored_fp = get_stored_seed_fingerprint(db_path)

    # 情况 1：还没有数据库。
    if current_rev is None:
        logger.info("当前没有数据库，将创建新库。")
        return {"action": "ok", "reseed": True, "reason": "当前没有数据库"}

    # 情况 2：数据库版本和当前分支兼容。
    if current_rev in known:
        if normalized_profile == "seed" and stored_fp == seed_fp and _has_legacy_dev_seed_residue(db_path):
            logger.info("检测到旧的开发测试种子残留，将重新灌种子。")
            return {"action": "ok", "reseed": True, "reason": "数据库版本兼容，但检测到旧的开发测试种子残留"}
        reseed = stored_fp != seed_fp
        if reseed:
            logger.info("种子定义已变化：%s -> %s，将重新灌种子。", stored_fp, seed_fp)
            return {"action": "ok", "reseed": True, "reason": "数据库版本兼容，但种子已变化"}
        return {"action": "ok", "reseed": False, "reason": "数据库版本兼容，种子匹配"}

    # 情况 3：数据库来自别的分支，直接删库重建。
    logger.warning(
        "数据库版本 %s 不在当前分支的迁移列表中：%s，准备删除并重建。",
        current_rev,
        sorted(known),
    )
    db_path.unlink()
    for suffix in ("-wal", "-shm"):
        wal = Path(str(db_path) + suffix)
        if wal.exists():
            wal.unlink()

    return {"action": "recreate", "reseed": True, "reason": "数据库版本不兼容，已重建"}
