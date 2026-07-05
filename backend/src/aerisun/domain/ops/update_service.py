from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from aerisun.core.runtime_version import get_runtime_version
from aerisun.core.settings import Settings, get_settings
from aerisun.core.time import shanghai_now
from aerisun.domain.ops.schemas import (
    SystemUpdateCheckWrite,
    SystemUpdateRequestRead,
    SystemUpdateStatusRead,
    SystemUpdateUpgradeWrite,
)

UPDATE_SCHEMA_VERSION = 1
UPDATE_DIRNAME = "update"
REQUESTS_DIRNAME = "requests"
UPDATER_SUPPORTED_FILENAME = "updater-supported.json"
STATUS_FILENAME = "status.json"
VERSION_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
ACTIVE_STATES = {"checking", "queued", "preflight", "running", "restarting"}


@dataclass
class UpdateRequestError(Exception):
    status_code: int
    detail: str


def _update_dir(settings: Settings | None = None) -> Path:
    resolved = settings or get_settings()
    return Path(resolved.data_dir) / UPDATE_DIRNAME


def _requests_dir(settings: Settings | None = None) -> Path:
    return _update_dir(settings) / REQUESTS_DIRNAME


def _read_json_file(path: Path) -> dict[str, object] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json_atomically(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        with suppress(OSError):
            os.unlink(tmp_name)
        raise


def _now_iso() -> str:
    return shanghai_now().isoformat()


def _current_version(settings: Settings | None = None) -> str:
    return get_runtime_version(settings)


def _updater_supported(settings: Settings | None = None) -> bool:
    marker = _update_dir(settings) / UPDATER_SUPPORTED_FILENAME
    payload = _read_json_file(marker)
    return bool(payload and payload.get("supported") is True)


def _base_status(settings: Settings | None = None) -> dict[str, object]:
    resolved = settings or get_settings()
    return {
        "schema_version": UPDATE_SCHEMA_VERSION,
        "state": "idle",
        "current_version": _current_version(resolved),
        "latest_version": None,
        "channel": resolved.install_channel or "stable",
        "update_available": False,
        "auto_update_supported": False,
        "auto_update_blocked_reason": None,
        "signature_verified": False,
        "release": None,
        "checked_at": None,
        "request_id": None,
        "run_id": None,
        "last_error": None,
        "recent_log": [],
    }


def get_update_status(settings: Settings | None = None) -> SystemUpdateStatusRead:
    base = _base_status(settings)
    if not _updater_supported(settings):
        base.update(
            {
                "state": "unsupported",
                "auto_update_supported": False,
                "auto_update_blocked_reason": "宿主机 updater 尚未安装或当前部署不是标准安装器布局。",
            }
        )
        return SystemUpdateStatusRead.model_validate(base)

    persisted = _read_json_file(_update_dir(settings) / STATUS_FILENAME) or {}
    merged = {**base, **persisted}
    merged["current_version"] = str(merged.get("current_version") or base["current_version"])
    if not merged.get("signature_verified"):
        merged["auto_update_supported"] = False
        merged["auto_update_blocked_reason"] = str(
            merged.get("auto_update_blocked_reason") or "更新元数据尚未通过签名校验，禁止后台自动升级。"
        )
    else:
        release = merged.get("release")
        bundle_sha256 = release.get("bundle_sha256") if isinstance(release, dict) else None
        trusted_public_key_b64 = release.get("trusted_public_key_b64") if isinstance(release, dict) else None
        if not isinstance(bundle_sha256, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", bundle_sha256):
            merged["auto_update_supported"] = False
            merged["auto_update_blocked_reason"] = "更新元数据缺少有效安装包 sha256，禁止后台自动升级。"
        elif not isinstance(trusted_public_key_b64, str) or not re.fullmatch(
            r"[A-Za-z0-9+/=]+", trusted_public_key_b64
        ):
            merged["auto_update_supported"] = False
            merged["auto_update_blocked_reason"] = "更新元数据缺少 trusted public key，禁止后台自动升级。"
    return SystemUpdateStatusRead.model_validate(merged)


def _pending_request_files(settings: Settings | None = None) -> list[Path]:
    requests_dir = _requests_dir(settings)
    if not requests_dir.exists():
        return []
    return sorted(path for path in requests_dir.glob("*.json") if path.is_file())


def _ensure_can_queue(settings: Settings | None = None) -> None:
    status = get_update_status(settings)
    if status.state == "unsupported":
        raise UpdateRequestError(409, status.auto_update_blocked_reason or "当前部署不支持后台自动升级。")
    if status.state in ACTIVE_STATES:
        raise UpdateRequestError(409, "已有更新任务正在执行，请等待完成后再操作。")
    if _pending_request_files(settings):
        raise UpdateRequestError(409, "已有待处理的更新请求，请稍后重试。")


def _write_request(payload: dict[str, object], settings: Settings | None = None) -> SystemUpdateRequestRead:
    request_id = str(payload["request_id"])
    request_path = _requests_dir(settings) / f"{request_id}.json"
    _write_json_atomically(request_path, payload)
    status = get_update_status(settings).model_dump(mode="json")
    status.update(
        {
            "state": "queued",
            "request_id": request_id,
            "last_error": None,
        }
    )
    if payload.get("action") == "upgrade" and payload.get("target_version"):
        status["latest_version"] = payload["target_version"]
        status["update_available"] = True
    _write_json_atomically(_update_dir(settings) / STATUS_FILENAME, status)
    return SystemUpdateRequestRead.model_validate({**payload, "state": "queued"})


def queue_update_check(payload: SystemUpdateCheckWrite, settings: Settings | None = None) -> SystemUpdateRequestRead:
    _ensure_can_queue(settings)
    request_id = uuid4().hex
    return _write_request(
        {
            "schema_version": UPDATE_SCHEMA_VERSION,
            "request_id": request_id,
            "action": "check",
            "force": bool(payload.force),
            "target_version": None,
            "created_at": _now_iso(),
        },
        settings,
    )


def queue_update_upgrade(
    payload: SystemUpdateUpgradeWrite, settings: Settings | None = None
) -> SystemUpdateRequestRead:
    if payload.target_version != payload.confirm_version:
        raise UpdateRequestError(400, "确认版本与目标版本不一致。")
    if not VERSION_RE.match(payload.target_version):
        raise UpdateRequestError(400, "目标版本号格式无效。")

    _ensure_can_queue(settings)
    status = get_update_status(settings)
    if status.latest_version != payload.target_version:
        raise UpdateRequestError(409, "目标版本与当前检测到的新版本不一致，请重新检查更新。")
    if not status.signature_verified:
        raise UpdateRequestError(409, "更新元数据尚未通过签名校验，禁止后台自动升级。")
    bundle_sha256 = status.release.bundle_sha256 if status.release else None
    if not bundle_sha256 or not re.fullmatch(r"[A-Fa-f0-9]{64}", bundle_sha256):
        raise UpdateRequestError(409, "更新元数据缺少有效安装包 sha256，禁止后台自动升级。")

    request_id = uuid4().hex
    return _write_request(
        {
            "schema_version": UPDATE_SCHEMA_VERSION,
            "request_id": request_id,
            "action": "upgrade",
            "target_version": payload.target_version,
            "bundle_sha256": bundle_sha256,
            "created_at": _now_iso(),
        },
        settings,
    )


def cancel_update_request(request_id: str, settings: Settings | None = None) -> None:
    if not re.fullmatch(r"[a-f0-9]{32}", request_id):
        raise UpdateRequestError(400, "更新请求 ID 无效。")
    request_path = _requests_dir(settings) / f"{request_id}.json"
    if not request_path.exists():
        raise UpdateRequestError(404, "更新请求不存在或已被执行器接管。")
    try:
        request_path.unlink()
    except OSError as exc:
        raise UpdateRequestError(409, "更新请求已被执行器接管，无法取消。") from exc
    status = get_update_status(settings).model_dump(mode="json")
    if status.get("state") == "queued" and status.get("request_id") == request_id:
        status["state"] = "available" if status.get("update_available") else "idle"
        status["request_id"] = None
        _write_json_atomically(_update_dir(settings) / STATUS_FILENAME, status)
