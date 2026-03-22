from __future__ import annotations

import os
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
BACKUP_SCRIPT = BACKEND_DIR / "scripts" / "backup.sh"
RESTORE_SCRIPT = BACKEND_DIR / "scripts" / "restore.sh"


def test_backup_script_exists():
    assert BACKUP_SCRIPT.exists()


def test_restore_script_exists():
    assert RESTORE_SCRIPT.exists()


def test_backup_script_fails_without_env():
    """备份脚本在缺少必需环境变量时应该退出（非零状态码）。"""
    result = subprocess.run(
        ["bash", str(BACKUP_SCRIPT)],
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0


def test_restore_script_fails_without_env():
    """恢复脚本在缺少必需环境变量时应该退出。"""
    result = subprocess.run(
        ["bash", str(RESTORE_SCRIPT)],
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
