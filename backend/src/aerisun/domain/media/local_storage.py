from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

from aerisun.domain.exceptions import StateConflict
from aerisun.domain.media.paths import assert_managed_local_path


def write_local_asset_file(storage_path: Path, content: bytes, *, sha256: str) -> None:
    target = assert_managed_local_path(storage_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha256:
            return
        raise StateConflict("目标资源文件已存在且内容不一致")

    temporary = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.stat().st_size != len(content):
            raise StateConflict("资源文件写入大小校验失败")
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != sha256:
            raise StateConflict("资源文件写入摘要校验失败")
        temporary.replace(target)
        descriptor = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)
