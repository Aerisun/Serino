from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import secrets
import shutil
import sqlite3
from collections import defaultdict
from contextlib import suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.media.models import (
    Asset,
    AssetLocalDeleteQueueItem,
    AssetMirrorQueueItem,
    AssetRemoteDeleteQueueItem,
    AssetRemoteUploadQueueItem,
)
from aerisun.domain.media.object_storage import (
    build_object_storage_maintenance_provider,
    get_or_create_object_storage_config,
)
from aerisun.domain.media.paths import (
    build_local_path,
    build_remote_object_key,
    build_resource_key,
    identity_from_asset,
    identity_from_resource_key,
    identity_from_upload,
    normalize_scope,
)
from aerisun.domain.media.references import (
    build_legacy_url_variants,
    classify_asset_usages,
    collect_registered_references,
    rewrite_registered_references,
    scan_unhandled_legacy_references,
)
from aerisun.domain.waline.service import (
    collect_waline_asset_references,
    rewrite_waline_asset_references,
)

migration_key = "2026_08_asset_storage_layout_v1"
schema_revision = "0019_asset_storage_layout"
summary = "整理资源范围、物理目录和永久访问地址"
mode = "blocking"
resource_keys: tuple[str, ...] = ()

_LEGACY_LOCAL_ROOTS = ("internal", "public")
_LEGACY_REMOTE_PREFIXES = ("internal/assets/", "public/assets/")
_MANIFEST_VERSION = 2
_MIGRATION_STATE_DIRNAME = ".data-migrations"
_ACTIVE_DELETE_STATUSES = ("queued", "running", "retrying", "failed")


@dataclass(frozen=True, slots=True)
class AssetMigrationPlan:
    asset_id: str
    old_resource_key: str
    old_local_path: Path
    old_local_source_present: bool
    old_remote_object_key: str | None
    old_remote_source_present: bool
    old_public_slug: str | None
    old_scope: str
    old_category: str
    old_storage_provider: str
    old_remote_status: str
    old_mirror_status: str
    old_sha256: str | None
    old_byte_size: int | None
    new_resource_key: str
    new_local_path: Path
    new_remote_object_key: str | None
    scope: str
    category: str
    content_type: str | None
    sha256: str
    byte_size: int
    legacy_urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssetStorageMigrationReport:
    migrated_asset_count: int
    rewritten_reference_count: int
    local_expected_keys: frozenset[str]
    local_actual_keys: frozenset[str]
    remote_expected_keys: frozenset[str]
    remote_actual_keys: frozenset[str]


def migration_manifest_path() -> Path:
    data_root = get_settings().data_dir.expanduser().resolve()
    state_dir = data_root / _MIGRATION_STATE_DIRNAME
    if state_dir.is_symlink():
        raise RuntimeError(f"资源迁移状态目录是符号链接，拒绝使用：{state_dir}")
    return state_dir / f"{migration_key}.json"


def _waline_backup_path() -> Path:
    return migration_manifest_path().with_suffix(".waline.db")


def _migration_temp_dir() -> Path:
    root = migration_manifest_path().parent / f"{migration_key}.tmp"
    if root.is_symlink():
        raise RuntimeError(f"资源迁移临时目录是符号链接，拒绝使用：{root}")
    return root


def _new_migration_temp_path(label: str) -> Path:
    root = _migration_temp_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{label}.{secrets.token_hex(8)}.tmp"


def _clear_migration_temp_files() -> None:
    root = _migration_temp_dir()
    if not root.exists():
        return
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError(f"资源迁移临时目录类型不安全：{root}")
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"资源迁移临时目录存在未知条目：{path}")
        path.unlink()
    root.rmdir()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _new_migration_temp_path("manifest")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_manifest() -> dict[str, Any] | None:
    path = migration_manifest_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"资源迁移恢复清单损坏：{path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"资源迁移恢复清单格式错误：{path}")
    if payload.get("version") != _MANIFEST_VERSION or payload.get("migration_key") != migration_key:
        raise RuntimeError(f"资源迁移恢复清单版本不匹配：{path}")
    return payload


def _snapshot_sqlite(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = _new_migration_temp_path("waline-snapshot")
    try:
        with sqlite3.connect(source) as source_connection, sqlite3.connect(temporary) as target_connection:
            source_connection.backup(target_connection)
        temporary.replace(target)
        with target.open("rb") as handle:
            os.fsync(handle.fileno())
        _fsync_directory(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_sqlite(source: Path, target: Path) -> None:
    if not source.is_file():
        return
    with sqlite3.connect(source) as source_connection, sqlite3.connect(target) as target_connection:
        source_connection.backup(target_connection)


def _remove_migration_state_files() -> None:
    _clear_migration_temp_files()
    migration_manifest_path().unlink(missing_ok=True)
    _waline_backup_path().unlink(missing_ok=True)
    state_dir = migration_manifest_path().parent
    with suppress(OSError):
        state_dir.rmdir()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plan_payload(plan: AssetMigrationPlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["old_local_path"] = str(plan.old_local_path)
    payload["new_local_path"] = str(plan.new_local_path)
    payload["legacy_urls"] = list(plan.legacy_urls)
    return payload


def _required_manifest_bool(raw: dict[str, Any], field: str) -> bool:
    value = raw.get(field)
    if not isinstance(value, bool):
        raise RuntimeError(f"资源迁移恢复清单的 {field} 字段错误")
    return value


def _manifest_content_type(raw: dict[str, Any]) -> str | None:
    value = raw.get("content_type")
    if value is None:
        return None
    if not isinstance(value, str) or "\n" in value or "\r" in value:
        raise RuntimeError("资源迁移恢复清单的 content_type 字段错误")
    normalized = value.strip()
    return normalized or None


def _manifest_optional_string(raw: dict[str, Any], field: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeError(f"资源迁移恢复清单的 {field} 字段错误")
    return value


def _manifest_optional_nonnegative_int(raw: dict[str, Any], field: str) -> int | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuntimeError(f"资源迁移恢复清单的 {field} 字段错误")
    return value


def _trusted_plans_from_manifest_payload(payload: dict[str, Any]) -> list[AssetMigrationPlan]:
    raw_plans = payload.get("plans")
    if not isinstance(raw_plans, list):
        raise RuntimeError("资源迁移恢复清单缺少 plans")
    plans: list[AssetMigrationPlan] = []
    seen_asset_ids: set[str] = set()
    for raw in raw_plans:
        if not isinstance(raw, dict):
            raise RuntimeError("资源迁移恢复清单的 plan 格式错误")
        try:
            plan = AssetMigrationPlan(
                asset_id=str(raw["asset_id"]),
                old_resource_key=str(raw["old_resource_key"]),
                old_local_path=Path(str(raw["old_local_path"])).expanduser().resolve(),
                old_local_source_present=_required_manifest_bool(raw, "old_local_source_present"),
                old_remote_object_key=(
                    None if raw.get("old_remote_object_key") is None else str(raw["old_remote_object_key"])
                ),
                old_remote_source_present=_required_manifest_bool(raw, "old_remote_source_present"),
                old_public_slug=_manifest_optional_string(raw, "old_public_slug"),
                old_scope=str(raw["old_scope"]),
                old_category=str(raw["old_category"]),
                old_storage_provider=str(raw["old_storage_provider"]),
                old_remote_status=str(raw["old_remote_status"]),
                old_mirror_status=str(raw["old_mirror_status"]),
                old_sha256=_manifest_optional_string(raw, "old_sha256"),
                old_byte_size=_manifest_optional_nonnegative_int(raw, "old_byte_size"),
                new_resource_key=str(raw["new_resource_key"]),
                new_local_path=Path(str(raw["new_local_path"])).expanduser().resolve(),
                new_remote_object_key=(
                    None if raw.get("new_remote_object_key") is None else str(raw["new_remote_object_key"])
                ),
                scope=normalize_scope(str(raw["scope"])),
                category=str(raw["category"]),
                content_type=_manifest_content_type(raw),
                sha256=str(raw["sha256"]).lower(),
                byte_size=int(raw["byte_size"]),
                legacy_urls=tuple(str(item) for item in raw.get("legacy_urls", [])),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeError("资源迁移恢复清单的 plan 字段错误") from exc
        if plan.asset_id in seen_asset_ids:
            raise RuntimeError(f"资源迁移恢复清单包含重复资源：{plan.asset_id}")
        seen_asset_ids.add(plan.asset_id)
        if plan.byte_size < 0 or len(plan.sha256) != 64 or any(char not in "0123456789abcdef" for char in plan.sha256):
            raise RuntimeError(f"资源迁移恢复清单的摘要或大小不可信：{plan.asset_id}")
        identity = identity_from_resource_key(plan.new_resource_key)
        if identity.asset_id != plan.asset_id:
            raise RuntimeError(f"资源迁移恢复清单的资源标识不一致：{plan.asset_id}")
        expected_local = build_local_path(identity, plan.scope)
        expected_remote = build_remote_object_key(identity, plan.scope) if plan.new_remote_object_key else None
        if plan.new_local_path != expected_local or plan.new_remote_object_key != expected_remote:
            raise RuntimeError(f"资源迁移恢复清单的目标地址不可信：{plan.asset_id}")
        plans.append(plan)
    _validate_plan_sources_and_targets(plans)
    return plans


def _manifest_legacy_delete_targets(
    payload: dict[str, Any],
    plans: list[AssetMigrationPlan],
) -> tuple[frozenset[Path], frozenset[str]]:
    raw_local = payload.get("legacy_delete_local_paths")
    raw_remote = payload.get("legacy_delete_remote_keys")
    if not isinstance(raw_local, list) or not all(isinstance(item, str) for item in raw_local):
        raise RuntimeError("资源迁移恢复清单的 legacy_delete_local_paths 字段错误")
    if not isinstance(raw_remote, list) or not all(isinstance(item, str) for item in raw_remote):
        raise RuntimeError("资源迁移恢复清单的 legacy_delete_remote_keys 字段错误")
    local_targets = frozenset(_normalize_legacy_delete_local_path(item) for item in raw_local)
    remote_targets = frozenset(_normalize_legacy_delete_remote_key(item) for item in raw_remote)
    if len(local_targets) != len(raw_local) or len(remote_targets) != len(raw_remote):
        raise RuntimeError("资源迁移恢复清单包含重复的旧资源删除目标")

    plan_local_paths = {plan.old_local_path for plan in plans} | {plan.new_local_path for plan in plans}
    plan_remote_keys = {
        key for plan in plans for key in (plan.old_remote_object_key, plan.new_remote_object_key) if key is not None
    }
    if local_targets & plan_local_paths or remote_targets & plan_remote_keys:
        raise RuntimeError("资源迁移恢复清单的待删除目标与已登记资源重叠")
    return local_targets, remote_targets


def _manifest_canonical_delete_targets(
    payload: dict[str, Any],
    plans: list[AssetMigrationPlan],
) -> tuple[frozenset[Path], frozenset[str]]:
    raw_local = payload.get("canonical_delete_local_paths")
    raw_remote = payload.get("canonical_delete_remote_keys")
    if not isinstance(raw_local, list) or not all(isinstance(item, str) for item in raw_local):
        raise RuntimeError("资源迁移恢复清单的 canonical_delete_local_paths 字段错误")
    if not isinstance(raw_remote, list) or not all(isinstance(item, str) for item in raw_remote):
        raise RuntimeError("资源迁移恢复清单的 canonical_delete_remote_keys 字段错误")
    local_targets = frozenset(Path(item).expanduser().resolve() for item in raw_local)
    remote_targets = frozenset(raw_remote)
    if len(local_targets) != len(raw_local) or len(remote_targets) != len(raw_remote):
        raise RuntimeError("资源迁移恢复清单包含重复的当前目录残留目标")
    for path in local_targets:
        _plan_for_canonical_local_copy(path, plans)
    for object_key in remote_targets:
        _plan_for_canonical_remote_copy(object_key, plans)
    return local_targets, remote_targets


def _plans_from_manifest(
    payload: dict[str, Any],
    session: Session,
    *,
    allow_extra_assets: bool = False,
    allow_current_targets: bool = False,
) -> list[AssetMigrationPlan]:
    raw_plans = payload.get("plans")
    if not isinstance(raw_plans, list):
        raise RuntimeError("资源迁移恢复清单缺少 plans")
    assets = {asset.id: asset for asset in session.scalars(select(Asset).order_by(Asset.id.asc())).all()}
    if len(raw_plans) > len(assets) or (not allow_extra_assets and len(raw_plans) != len(assets)):
        raise RuntimeError("资源迁移恢复清单与当前资源数量不一致")

    media_root = get_settings().media_dir.expanduser().resolve()
    plans: list[AssetMigrationPlan] = []
    for raw in raw_plans:
        if not isinstance(raw, dict):
            raise RuntimeError("资源迁移恢复清单的 plan 格式错误")
        try:
            plan = AssetMigrationPlan(
                asset_id=str(raw["asset_id"]),
                old_resource_key=str(raw["old_resource_key"]),
                old_local_path=Path(str(raw["old_local_path"])).expanduser().resolve(),
                old_local_source_present=_required_manifest_bool(raw, "old_local_source_present"),
                old_remote_object_key=(
                    None if raw.get("old_remote_object_key") is None else str(raw["old_remote_object_key"])
                ),
                old_remote_source_present=_required_manifest_bool(raw, "old_remote_source_present"),
                old_public_slug=_manifest_optional_string(raw, "old_public_slug"),
                old_scope=str(raw["old_scope"]),
                old_category=str(raw["old_category"]),
                old_storage_provider=str(raw["old_storage_provider"]),
                old_remote_status=str(raw["old_remote_status"]),
                old_mirror_status=str(raw["old_mirror_status"]),
                old_sha256=_manifest_optional_string(raw, "old_sha256"),
                old_byte_size=_manifest_optional_nonnegative_int(raw, "old_byte_size"),
                new_resource_key=str(raw["new_resource_key"]),
                new_local_path=Path(str(raw["new_local_path"])).expanduser().resolve(),
                new_remote_object_key=(
                    None if raw.get("new_remote_object_key") is None else str(raw["new_remote_object_key"])
                ),
                scope=str(raw["scope"]),
                category=str(raw["category"]),
                content_type=_manifest_content_type(raw),
                sha256=str(raw["sha256"]),
                byte_size=int(raw["byte_size"]),
                legacy_urls=tuple(str(item) for item in raw.get("legacy_urls", [])),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeError("资源迁移恢复清单的 plan 字段错误") from exc
        asset = assets.get(plan.asset_id)
        if asset is None:
            raise RuntimeError(f"资源迁移恢复清单包含未知资源：{plan.asset_id}")
        identity = identity_from_asset(asset)
        if allow_current_targets:
            if asset.byte_size is not None and int(asset.byte_size) != plan.byte_size:
                raise RuntimeError(f"资源当前大小与迁移清单不一致：{plan.asset_id}")
            if asset.sha256 and str(asset.sha256).lower() != plan.sha256:
                raise RuntimeError(f"资源当前摘要与迁移清单不一致：{plan.asset_id}")
            current_scope = normalize_scope(str(asset.scope))
            current_local_path = build_local_path(identity, current_scope)
            current_remote_key = build_remote_object_key(identity, current_scope) if asset.remote_object_key else None
            if Path(asset.storage_path).expanduser().resolve() != current_local_path:
                raise RuntimeError(f"资源当前本地地址与范围不一致：{plan.asset_id}")
            if (str(asset.remote_object_key) if asset.remote_object_key else None) != current_remote_key:
                raise RuntimeError(f"资源当前 OSS Key 与范围不一致：{plan.asset_id}")
            plan = replace(
                plan,
                old_local_path=current_local_path
                if plan.old_resource_key == plan.new_resource_key
                else plan.old_local_path,
                old_remote_object_key=(
                    current_remote_key if plan.old_resource_key == plan.new_resource_key else plan.old_remote_object_key
                ),
                new_local_path=current_local_path,
                new_remote_object_key=current_remote_key,
                scope=current_scope,
                category=str(asset.category),
            )
        expected_resource_key = build_resource_key(identity)
        expected_local_path = build_local_path(identity, plan.scope)
        expected_remote_key = build_remote_object_key(identity, plan.scope) if plan.new_remote_object_key else None
        if (
            plan.new_resource_key != expected_resource_key
            or plan.new_local_path != expected_local_path
            or plan.new_remote_object_key != expected_remote_key
        ):
            raise RuntimeError(f"资源迁移恢复清单的目标地址不可信：{plan.asset_id}")
        try:
            plan.old_local_path.relative_to(media_root)
            plan.new_local_path.relative_to(media_root)
        except ValueError as exc:
            raise RuntimeError(f"资源迁移恢复清单越出媒体目录：{plan.asset_id}") from exc
        if plan.old_resource_key != plan.new_resource_key:
            old_key_path = Path(*plan.old_resource_key.split("/"))
            if (
                old_key_path.is_absolute()
                or ".." in old_key_path.parts
                or plan.old_local_path != (media_root / old_key_path).resolve()
            ):
                raise RuntimeError(f"资源迁移恢复清单的旧本地地址不可信：{plan.asset_id}")
        if plan.old_remote_object_key and not (
            plan.old_remote_object_key.startswith(_LEGACY_REMOTE_PREFIXES)
            or plan.old_remote_object_key == plan.new_remote_object_key
        ):
            raise RuntimeError(f"资源迁移恢复清单的旧 OSS Key 不可信：{plan.asset_id}")
        if (
            plan.old_remote_object_key
            and plan.old_remote_object_key != plan.new_remote_object_key
            and plan.old_remote_object_key != plan.old_resource_key
        ):
            raise RuntimeError(f"资源迁移恢复清单的旧 OSS Key 与资源键不一致：{plan.asset_id}")
        if (
            str(asset.resource_key) != plan.new_resource_key
            or asset.public_slug is not None
            or Path(asset.storage_path).expanduser().resolve() != plan.new_local_path
            or str(asset.scope) != plan.scope
            or str(asset.category) != plan.category
            or (str(asset.remote_object_key) if asset.remote_object_key else None) != plan.new_remote_object_key
        ):
            raise RuntimeError(f"资源迁移恢复清单与数据库状态不一致：{plan.asset_id}")
        plans.append(plan)
    _validate_plan_sources_and_targets(plans)
    return plans


def _atomic_copy(source: Path, target: Path, *, expected_sha256: str, expected_size: int) -> bool:
    if target.exists():
        if not target.is_file() or target.stat().st_size != expected_size or _file_sha256(target) != expected_sha256:
            raise RuntimeError(f"目标本地资源内容冲突：{target}")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = _new_migration_temp_path("local-copy")
    try:
        with source.open("rb") as source_handle, temporary.open("xb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        if temporary.stat().st_size != expected_size or _file_sha256(temporary) != expected_sha256:
            raise RuntimeError(f"目标本地资源校验失败：{target}")
        temporary.replace(target)
        _fsync_directory(target.parent)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _legacy_url_mapping(assets: list[Asset]) -> tuple[dict[str, str], dict[str, str]]:
    settings = get_settings()
    site_urls = (settings.site_url,)
    url_to_asset_id: dict[str, str] = {}
    replacements: dict[str, str] = {}
    claim_priorities: dict[str, int] = {}
    for asset in assets:
        identity = identity_from_asset(asset)
        canonical_url = f"/media/{build_resource_key(identity)}"
        canonical_variants = {canonical_url}
        canonical_variants.update(
            f"{str(site_url).strip().rstrip('/')}{canonical_url}"
            for site_url in site_urls
            if str(site_url or "").strip()
        )
        exact_resource_path = f"/media/{str(asset.resource_key).strip().lstrip('/')}"
        public_slug = str(asset.public_slug or "").strip().lstrip("/")
        preferred_paths = {exact_resource_path}
        if public_slug and "/" not in public_slug:
            preferred_paths.add(f"/media/{public_slug}")
        preferred_variants = set(preferred_paths)
        preferred_variants.update(
            f"{str(site_url).strip().rstrip('/')}{path}"
            for site_url in site_urls
            if str(site_url or "").strip()
            for path in preferred_paths
        )
        for legacy_url in build_legacy_url_variants(asset, site_urls=site_urls):
            if legacy_url in canonical_variants:
                continue
            priority = 2 if legacy_url in preferred_variants else 1
            existing_asset_id = url_to_asset_id.get(legacy_url)
            if existing_asset_id is not None and existing_asset_id != asset.id:
                existing_priority = claim_priorities[legacy_url]
                if existing_priority == priority:
                    raise RuntimeError(f"旧资源地址映射不唯一：{legacy_url}")
                if existing_priority > priority:
                    continue
            url_to_asset_id[legacy_url] = asset.id
            replacements[legacy_url] = canonical_url
            claim_priorities[legacy_url] = priority
    return url_to_asset_id, replacements


def _classification_for_asset(asset: Asset, usages: set[str]) -> tuple[str, str]:
    classification = classify_asset_usages(usages)
    if classification.usages:
        return classification.scope, classification.category
    if asset.scope == "system":
        return "system", str(asset.category or "general")
    if str(asset.category or "").strip().lower() == "comment":
        return "visitor", "comment"
    return "user", "general"


def _validate_plan_sources_and_targets(plans: list[AssetMigrationPlan]) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    expected_targets = [plan.new_local_path for plan in plans]
    if len(expected_targets) != len(set(expected_targets)):
        raise RuntimeError("多个资源的目标本地地址发生冲突，拒绝迁移")
    expected_target_set = set(expected_targets)

    for plan in plans:
        if plan.old_remote_source_present and plan.old_remote_object_key is None:
            raise RuntimeError(f"资源标记存在旧 OSS 来源但缺少 Key：{plan.asset_id}")
        try:
            plan.old_local_path.relative_to(media_root)
            plan.new_local_path.relative_to(media_root)
        except ValueError as exc:
            raise RuntimeError(f"资源本地地址越出媒体目录，拒绝迁移：{plan.asset_id}") from exc

        is_legacy = plan.old_resource_key != plan.new_resource_key
        if is_legacy:
            if not plan.old_resource_key.startswith(_LEGACY_REMOTE_PREFIXES):
                raise RuntimeError(f"资源旧键不属于受管旧目录，拒绝迁移：{plan.asset_id}")
            old_relative = Path(*plan.old_resource_key.split("/"))
            expected_old_local = (media_root / old_relative).resolve()
            if plan.old_local_path != expected_old_local:
                raise RuntimeError(f"资源旧本地地址与资源键不一致，不可信：{plan.asset_id}")
            if plan.old_remote_object_key is not None and plan.old_remote_object_key != plan.old_resource_key:
                raise RuntimeError(f"资源旧 OSS Key 与资源键不一致，不可信：{plan.asset_id}")
        elif plan.old_local_path != plan.new_local_path:
            raise RuntimeError(f"当前资源的本地地址与范围不一致，不可信：{plan.asset_id}")
        elif plan.old_remote_object_key is not None and plan.old_remote_object_key != plan.new_remote_object_key:
            raise RuntimeError(f"当前资源的 OSS Key 与范围不一致，不可信：{plan.asset_id}")

        if plan.old_local_path != plan.new_local_path and plan.old_local_path in expected_target_set:
            raise RuntimeError(f"资源旧本地地址与另一个资源的目标路径重叠：{plan.asset_id}")


def _validate_legacy_media_tree(media_root: Path) -> None:
    media_root.mkdir(parents=True, exist_ok=True)
    allowed_roots = {"assets", *_LEGACY_LOCAL_ROOTS}
    for child in media_root.iterdir():
        if child.is_symlink():
            raise RuntimeError(f"媒体根目录存在符号链接，拒绝迁移：{child}")
        if child.name not in allowed_roots:
            raise RuntimeError(f"媒体根目录存在未知条目，拒绝迁移：{child}")
        if not child.is_dir():
            raise RuntimeError(f"媒体根目录存在非常规条目，拒绝迁移：{child}")
    for root_name in _LEGACY_LOCAL_ROOTS:
        root = media_root / root_name
        if not root.exists():
            continue
        for child in root.iterdir():
            if child.is_symlink() or not child.is_dir() or child.name != "assets":
                raise RuntimeError(f"旧资源目录存在未知条目，拒绝迁移：{child}")


def _looks_like_staging_artifact(parts: tuple[str, ...]) -> bool:
    return any(part.startswith(".") or part.endswith((".tmp", ".part", ".partial")) for part in parts)


def _normalize_legacy_delete_local_path(raw_path: str) -> Path:
    media_root = get_settings().media_dir.expanduser().resolve()
    candidate = Path(raw_path).expanduser()
    if candidate.is_symlink():
        raise RuntimeError(f"本地删除队列目标是符号链接，拒绝迁移：{candidate}")
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(media_root)
    except ValueError as exc:
        raise RuntimeError(f"本地删除队列目标越出媒体目录，拒绝迁移：{resolved}") from exc
    if len(relative.parts) < 3 or relative.parts[0] not in _LEGACY_LOCAL_ROOTS or relative.parts[1] != "assets":
        raise RuntimeError(f"本地删除队列目标不属于旧资源目录，拒绝迁移：{resolved}")
    return resolved


def _normalize_legacy_delete_remote_key(raw_key: str) -> str:
    object_key = str(raw_key).strip().lstrip("/")
    relative = Path(*object_key.split("/"))
    if (
        not object_key.startswith(_LEGACY_REMOTE_PREFIXES)
        or relative.is_absolute()
        or ".." in relative.parts
        or object_key.endswith("/")
    ):
        raise RuntimeError(f"OSS 删除队列目标不属于旧资源目录，拒绝迁移：{raw_key}")
    return object_key


def _collect_active_legacy_delete_targets(
    session: Session,
    provider: Any | None,
) -> tuple[frozenset[Path], frozenset[str]]:
    assets = list(session.scalars(select(Asset).order_by(Asset.id.asc())).all())
    registered_paths = {Path(asset.storage_path).expanduser().resolve() for asset in assets}
    registered_remote_keys = {str(asset.remote_object_key) for asset in assets if asset.remote_object_key}

    local_targets: set[Path] = set()
    local_items = session.scalars(
        select(AssetLocalDeleteQueueItem).where(AssetLocalDeleteQueueItem.status.in_(_ACTIVE_DELETE_STATUSES))
    ).all()
    for item in local_items:
        target = _normalize_legacy_delete_local_path(str(item.storage_path))
        if target in registered_paths:
            raise RuntimeError(f"本地删除队列仍指向已登记资源，拒绝迁移：{target}")
        if not target.exists():
            continue
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f"本地删除队列目标类型不安全，拒绝迁移：{target}")
        local_targets.add(target)

    remote_items = session.scalars(
        select(AssetRemoteDeleteQueueItem).where(AssetRemoteDeleteQueueItem.status.in_(_ACTIVE_DELETE_STATUSES))
    ).all()
    normalized_remote_targets = {_normalize_legacy_delete_remote_key(str(item.object_key)) for item in remote_items}
    conflicting_remote = normalized_remote_targets & registered_remote_keys
    if conflicting_remote:
        raise RuntimeError(f"OSS 删除队列仍指向已登记资源，拒绝迁移：{sorted(conflicting_remote)[0]}")
    if normalized_remote_targets and provider is None:
        raise RuntimeError("检测到待删除 OSS 旧资源，但 OSS 当前不可用；迁移已停止")
    remote_targets = frozenset(
        object_key
        for object_key in normalized_remote_targets
        if provider is not None and _remote_entry(provider, object_key) is not None
    )
    return frozenset(local_targets), remote_targets


def _adopt_unregistered_local_assets(
    session: Session,
    provider: Any | None,
    *,
    ignored_paths: frozenset[Path],
) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    _validate_legacy_media_tree(media_root)
    assets = list(session.scalars(select(Asset).order_by(Asset.id.asc())).all())
    registered_paths = {Path(asset.storage_path).expanduser().resolve() for asset in assets}
    registered_keys = {str(asset.resource_key) for asset in assets}

    for root_name in _LEGACY_LOCAL_ROOTS:
        root = media_root / root_name / "assets"
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise RuntimeError(f"旧资源目录存在符号链接，拒绝迁移：{path}")
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in registered_paths or resolved in ignored_paths:
                continue
            resource_key = resolved.relative_to(media_root).as_posix()
            if _looks_like_staging_artifact(tuple(resolved.relative_to(media_root).parts)):
                raise RuntimeError(f"旧资源目录存在疑似临时文件，拒绝自动收编：{resource_key}")
            if resource_key in registered_keys:
                raise RuntimeError(f"未登记文件与已有资源键冲突：{resource_key}")
            byte_size = resolved.stat().st_size
            sha256 = _file_sha256(resolved)
            asset_id = str(uuid5(NAMESPACE_URL, f"serino-asset-layout-v1:{resource_key}:{sha256}"))
            identity = identity_from_upload(
                asset_id=asset_id,
                file_name=resolved.name,
                mime_type=None,
            )
            remote_head = _remote_entry(provider, resource_key) if provider is not None else None
            if remote_head is not None and remote_head.content_length != byte_size:
                raise RuntimeError(f"未登记资源的本地和 OSS 大小不一致：{resource_key}")
            session.add(
                Asset(
                    id=identity.asset_id,
                    file_name=resolved.name,
                    resource_key=resource_key,
                    visibility="public" if root_name == "public" else "internal",
                    scope="user",
                    category="general",
                    storage_path=str(resolved),
                    byte_size=byte_size,
                    sha256=sha256,
                    storage_provider="bitiful" if remote_head is not None else "local",
                    remote_object_key=resource_key if remote_head is not None else None,
                    remote_status="available" if remote_head is not None else "none",
                    mirror_status="completed",
                )
            )
            registered_paths.add(resolved)
            registered_keys.add(resource_key)
    session.flush()


def _adopt_unregistered_remote_assets(
    session: Session,
    provider: Any,
    *,
    downloaded: list[Path],
    ignored_local_paths: frozenset[Path],
    ignored_remote_keys: frozenset[str],
) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    assets = list(session.scalars(select(Asset).order_by(Asset.id.asc())).all())
    registered_keys = {str(asset.remote_object_key) for asset in assets if asset.remote_object_key}
    entries = {
        entry.object_key: entry
        for prefix in _LEGACY_REMOTE_PREFIXES
        for entry in provider.list_objects(prefix=prefix)
        if not (entry.object_key.endswith("/") and entry.content_length == 0)
    }

    for object_key in sorted(set(entries) - registered_keys - ignored_remote_keys):
        relative = Path(*object_key.split("/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"OSS 旧资源 Key 不安全，拒绝迁移：{object_key}")
        if _looks_like_staging_artifact(tuple(relative.parts)):
            raise RuntimeError(f"OSS 旧目录存在疑似临时对象，拒绝自动收编：{object_key}")
        local_path = (media_root / relative).resolve()
        try:
            local_path.relative_to(media_root)
        except ValueError as exc:
            raise RuntimeError(f"OSS 旧资源越出媒体目录，拒绝迁移：{object_key}") from exc
        if local_path.exists():
            raise RuntimeError(f"未登记 OSS 对象与本地路径冲突：{object_key}")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = _new_migration_temp_path("adopt-remote")
        try:
            provider.download_to_local(
                object_key=object_key,
                dest_path=temporary,
                bandwidth_limit_bps=None,
            )
            if not temporary.is_file() or temporary.stat().st_size != entries[object_key].content_length:
                raise RuntimeError(f"未登记 OSS 对象下载校验失败：{object_key}")
            temporary.replace(local_path)
            downloaded.append(local_path)
        finally:
            temporary.unlink(missing_ok=True)

    if entries.keys() - registered_keys:
        _adopt_unregistered_local_assets(
            session,
            provider,
            ignored_paths=ignored_local_paths,
        )


def _plan_for_canonical_local_copy(path: Path, plans: list[AssetMigrationPlan]) -> AssetMigrationPlan:
    media_root = get_settings().media_dir.expanduser().resolve()
    try:
        relative = path.relative_to(media_root)
        if len(relative.parts) != 3 or relative.parts[0] != "assets":
            raise ValueError
        scope = normalize_scope(relative.parts[1])
        identity = identity_from_resource_key(f"assets/{relative.parts[2]}")
    except (ValueError, ValidationError) as exc:
        raise RuntimeError(f"当前资源目录存在不可信文件：{path}") from exc
    plan = next((item for item in plans if item.asset_id == identity.asset_id), None)
    if plan is None or build_local_path(identity, scope) != path or plan.new_local_path == path:
        raise RuntimeError(f"当前资源目录存在未登记文件：{path}")
    return plan


def _plan_for_canonical_remote_copy(object_key: str, plans: list[AssetMigrationPlan]) -> AssetMigrationPlan:
    parts = tuple(object_key.split("/"))
    try:
        if len(parts) != 3 or parts[0] != "assets":
            raise ValueError
        scope = normalize_scope(parts[1])
        identity = identity_from_resource_key(f"assets/{parts[2]}")
    except (ValueError, ValidationError) as exc:
        raise RuntimeError(f"OSS 当前资源目录存在不可信对象：{object_key}") from exc
    plan = next((item for item in plans if item.asset_id == identity.asset_id), None)
    if (
        plan is None
        or build_remote_object_key(identity, scope) != object_key
        or plan.new_remote_object_key == object_key
    ):
        raise RuntimeError(f"OSS 当前资源目录存在未登记对象：{object_key}")
    return plan


def _collect_verified_stale_canonical_copies(
    plans: list[AssetMigrationPlan],
    provider: Any | None,
) -> tuple[frozenset[Path], frozenset[str]]:
    media_root = get_settings().media_dir.expanduser().resolve()
    expected_local = {plan.new_local_path.relative_to(media_root).as_posix() for plan in plans}
    stale_local: set[Path] = set()
    for relative_key in sorted(_actual_local_keys(media_root) - expected_local):
        path = (media_root / Path(*relative_key.split("/"))).resolve()
        plan = _plan_for_canonical_local_copy(path, plans)
        if path.stat().st_size != plan.byte_size or _file_sha256(path) != plan.sha256:
            raise RuntimeError(f"当前目录残留副本内容不一致，拒绝清理：{path}")
        stale_local.add(path)

    stale_remote: set[str] = set()
    if provider is not None:
        expected_remote = {plan.new_remote_object_key for plan in plans if plan.new_remote_object_key}
        actual_remote = {
            entry.object_key
            for entry in provider.list_objects(prefix="assets/")
            if not (entry.object_key.endswith("/") and entry.content_length == 0)
        }
        for object_key in sorted(actual_remote - expected_remote):
            plan = _plan_for_canonical_remote_copy(object_key, plans)
            _verify_remote_object(provider, object_key=object_key, plan=plan)
            stale_remote.add(object_key)
    return frozenset(stale_local), frozenset(stale_remote)


def _build_plans(
    session: Session,
    *,
    waline_db_path: Path,
    provider: Any | None,
    downloaded_legacy_sources: list[Path],
    mirror_local_assets_to_oss: bool,
) -> tuple[
    list[AssetMigrationPlan],
    dict[str, str],
    set[str],
    frozenset[Path],
    frozenset[str],
    frozenset[Path],
    frozenset[str],
]:
    pending_local_deletes, pending_remote_deletes = _collect_active_legacy_delete_targets(session, provider)
    _adopt_unregistered_local_assets(
        session,
        provider,
        ignored_paths=pending_local_deletes,
    )
    if provider is not None:
        _adopt_unregistered_remote_assets(
            session,
            provider,
            downloaded=downloaded_legacy_sources,
            ignored_local_paths=pending_local_deletes,
            ignored_remote_keys=pending_remote_deletes,
        )
    assets = list(session.scalars(select(Asset).order_by(Asset.id.asc())).all())
    remote_assets = [asset for asset in assets if str(asset.remote_object_key or "").strip()]
    if provider is None and remote_assets:
        raise RuntimeError(f"检测到 {len(remote_assets)} 个 OSS 资源，但 OSS 当前不可用；为避免远端残留，迁移已停止")
    url_to_asset_id, replacements = _legacy_url_mapping(assets)
    old_urls = set(url_to_asset_id)

    unhandled = scan_unhandled_legacy_references(session, old_urls)
    if unhandled:
        first = unhandled[0]
        raise RuntimeError(
            f"发现未注册的旧资源引用：{first.table}.{first.column} row={first.row_id} url={first.matched_url}"
        )

    usages_by_asset: dict[str, set[str]] = defaultdict(set)
    for reference in collect_registered_references(session, url_to_asset_id):
        if reference.usage:
            usages_by_asset[reference.asset_id].add(reference.usage)
    for reference in collect_waline_asset_references(waline_db_path, url_to_asset_id):
        usages_by_asset[reference.asset_id].add(reference.usage)

    if provider is not None:
        registered_old_remote_keys = {
            str(asset.remote_object_key)
            for asset in assets
            if str(asset.remote_object_key or "").startswith(_LEGACY_REMOTE_PREFIXES)
        }
        actual_old_remote_keys = {
            entry.object_key
            for prefix in _LEGACY_REMOTE_PREFIXES
            for entry in provider.list_objects(prefix=prefix)
            if not (entry.object_key.endswith("/") and entry.content_length == 0)
        }
        unregistered_remote_keys = actual_old_remote_keys - registered_old_remote_keys - pending_remote_deletes
        if unregistered_remote_keys:
            raise RuntimeError(f"OSS 旧目录存在未登记对象：{sorted(unregistered_remote_keys)[0]}")

    plans: list[AssetMigrationPlan] = []
    for asset in assets:
        identity = identity_from_asset(asset)
        new_resource_key = build_resource_key(identity)
        is_current = str(asset.resource_key) == new_resource_key
        scope, category = (
            (str(asset.scope), str(asset.category))
            if is_current
            else _classification_for_asset(asset, usages_by_asset.get(asset.id, set()))
        )
        raw_old_local_path = Path(asset.storage_path).expanduser()
        if raw_old_local_path.is_symlink():
            raise RuntimeError(f"资源本地地址是符号链接，拒绝迁移：{asset.id}")
        old_local_path = raw_old_local_path.resolve()
        old_remote_key = str(asset.remote_object_key or "").strip() or None
        old_local_source_present = old_local_path.exists() and old_local_path.is_file()
        remote_head = (
            _remote_entry(provider, old_remote_key) if provider is not None and old_remote_key is not None else None
        )
        old_remote_source_present = remote_head is not None

        if old_local_source_present:
            byte_size = old_local_path.stat().st_size
            sha256 = _file_sha256(old_local_path)
        elif remote_head is not None:
            if remote_head.content_length is None:
                raise RuntimeError(f"无法确认远端资源大小：{old_remote_key}")
            byte_size = int(remote_head.content_length)
            sha256 = str(asset.sha256 or "")
            if not sha256:
                raise RuntimeError(f"远端资源缺少 SHA-256，无法安全迁移：{asset.id}")
        else:
            raise RuntimeError(f"资源既没有本地文件也没有可用远端对象：{asset.id}")

        if asset.byte_size is not None and int(asset.byte_size) != byte_size:
            raise RuntimeError(f"资源大小与数据库不一致：{asset.id}")
        if asset.sha256 and str(asset.sha256).lower() != sha256:
            raise RuntimeError(f"资源摘要与数据库不一致：{asset.id}")

        plans.append(
            AssetMigrationPlan(
                asset_id=asset.id,
                old_resource_key=str(asset.resource_key),
                old_local_path=old_local_path,
                old_local_source_present=old_local_source_present,
                old_remote_object_key=old_remote_key,
                old_remote_source_present=old_remote_source_present,
                old_public_slug=str(asset.public_slug) if asset.public_slug is not None else None,
                old_scope=str(asset.scope),
                old_category=str(asset.category),
                old_storage_provider=str(asset.storage_provider),
                old_remote_status=str(asset.remote_status),
                old_mirror_status=str(asset.mirror_status),
                old_sha256=str(asset.sha256).lower() if asset.sha256 else None,
                old_byte_size=int(asset.byte_size) if asset.byte_size is not None else None,
                new_resource_key=new_resource_key,
                new_local_path=build_local_path(identity, scope),
                new_remote_object_key=(
                    build_remote_object_key(identity, scope)
                    if provider is not None and (old_remote_key is not None or mirror_local_assets_to_oss)
                    else None
                ),
                scope=scope,
                category=category,
                content_type=(str(asset.mime_type).strip() if asset.mime_type else None)
                or mimetypes.guess_type(str(asset.file_name))[0],
                sha256=sha256,
                byte_size=byte_size,
                legacy_urls=build_legacy_url_variants(asset, site_urls=(get_settings().site_url,))
                if not is_current
                else (),
            )
        )
    _validate_plan_sources_and_targets(plans)
    stale_local_copies, stale_remote_copies = _collect_verified_stale_canonical_copies(plans, provider)
    return (
        plans,
        replacements,
        old_urls,
        pending_local_deletes,
        pending_remote_deletes,
        stale_local_copies,
        stale_remote_copies,
    )


def _prepare_local_targets(
    plans: list[AssetMigrationPlan],
    provider: Any | None,
    *,
    created: list[Path],
) -> None:
    for plan in plans:
        if plan.old_local_path == plan.new_local_path:
            continue
        if plan.old_local_path.exists() and plan.old_local_path.is_file():
            if _atomic_copy(
                plan.old_local_path,
                plan.new_local_path,
                expected_sha256=plan.sha256,
                expected_size=plan.byte_size,
            ):
                created.append(plan.new_local_path)
            continue
        if provider is None or not plan.old_remote_object_key or not plan.old_remote_source_present:
            raise RuntimeError(f"无法准备本地资源：{plan.asset_id}")
        temporary = _new_migration_temp_path(f"mirror-{plan.asset_id}")
        try:
            provider.download_to_local(
                object_key=plan.old_remote_object_key,
                dest_path=temporary,
                bandwidth_limit_bps=None,
            )
            if temporary.stat().st_size != plan.byte_size or _file_sha256(temporary) != plan.sha256:
                raise RuntimeError(f"远端下载后的本地资源校验失败：{plan.asset_id}")
            plan.new_local_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.replace(plan.new_local_path)
            created.append(plan.new_local_path)
        finally:
            temporary.unlink(missing_ok=True)


def _remote_entry(provider: Any, object_key: str) -> Any | None:
    finder = getattr(provider, "find_object", None)
    if not callable(finder):
        raise RuntimeError("OSS 维护实现缺少严格的对象存在性检查，拒绝迁移")
    return finder(object_key=object_key)


def _verify_remote_object(provider: Any, *, object_key: str, plan: AssetMigrationPlan) -> None:
    temporary = _new_migration_temp_path(f"verify-{plan.asset_id}")
    try:
        provider.download_to_local(
            object_key=object_key,
            dest_path=temporary,
            bandwidth_limit_bps=None,
        )
        if temporary.stat().st_size != plan.byte_size or _file_sha256(temporary) != plan.sha256:
            raise RuntimeError(f"目标 OSS 对象摘要校验失败：{object_key}")
    finally:
        temporary.unlink(missing_ok=True)


def _prepare_remote_targets(
    plans: list[AssetMigrationPlan],
    provider: Any | None,
    *,
    created: list[str],
) -> None:
    if provider is None:
        return
    for plan in plans:
        target_key = plan.new_remote_object_key
        if target_key is None:
            continue
        existing = _remote_entry(provider, target_key)
        if existing is not None:
            if existing.content_length != plan.byte_size:
                raise RuntimeError(f"目标 OSS 对象内容冲突：{target_key}")
            _verify_remote_object(provider, object_key=target_key, plan=plan)
            continue
        try:
            if plan.old_remote_object_key and plan.old_remote_source_present:
                head = provider.copy_object(
                    source_key=plan.old_remote_object_key,
                    object_key=target_key,
                    content_type=plan.content_type,
                )
            else:
                head = provider.upload_local_file(
                    object_key=target_key,
                    source_path=plan.new_local_path,
                    content_type=plan.content_type,
                )
        except Exception:
            if _remote_entry(provider, target_key) is not None:
                created.append(target_key)
            raise
        if head.content_length != plan.byte_size:
            provider.delete_object(object_key=target_key)
            raise RuntimeError(f"目标 OSS 对象大小校验失败：{target_key}")
        created.append(target_key)
        _verify_remote_object(provider, object_key=target_key, plan=plan)


def _remove_empty_legacy_directories(media_root: Path) -> None:
    for root_name in _LEGACY_LOCAL_ROOTS:
        root = media_root / root_name
        if not root.exists() or root.is_symlink():
            continue
        directories = sorted(
            (path for path in root.rglob("*") if path.is_dir() and not path.is_symlink()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            with suppress(OSError):
                directory.rmdir()
        with suppress(OSError):
            root.rmdir()


def _remove_empty_asset_directories(media_root: Path) -> None:
    root = media_root / "assets"
    if not root.exists() or root.is_symlink():
        return
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir() and not path.is_symlink()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        with suppress(OSError):
            directory.rmdir()
    with suppress(OSError):
        root.rmdir()


def _actual_local_keys(media_root: Path) -> frozenset[str]:
    assets_root = media_root / "assets"
    if not assets_root.exists():
        return frozenset()
    if assets_root.is_symlink() or not assets_root.is_dir():
        raise RuntimeError(f"本地资源根目录类型不安全：{assets_root}")
    for path in assets_root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"本地资源目录存在符号链接，拒绝继续迁移：{path}")
        if not path.is_file() and not path.is_dir():
            raise RuntimeError(f"本地资源目录存在非常规条目，拒绝继续迁移：{path}")
    return frozenset(path.relative_to(media_root).as_posix() for path in assets_root.rglob("*") if path.is_file())


def _actual_legacy_local_keys(media_root: Path) -> frozenset[str]:
    _validate_legacy_media_tree(media_root)
    keys: set[str] = set()
    for root_name in _LEGACY_LOCAL_ROOTS:
        root = media_root / root_name / "assets"
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink():
                raise RuntimeError(f"旧资源目录存在符号链接，拒绝继续迁移：{path}")
            if path.is_file():
                keys.add(path.relative_to(media_root).as_posix())
            elif not path.is_dir():
                raise RuntimeError(f"旧资源目录存在非常规条目，拒绝继续迁移：{path}")
    return frozenset(keys)


def _audit_prepared_state(
    session: Session,
    *,
    plans: list[AssetMigrationPlan],
    old_urls: set[str],
    waline_db_path: Path,
    provider: Any | None,
    legacy_delete_local_paths: frozenset[Path],
    legacy_delete_remote_keys: frozenset[str],
    canonical_delete_local_paths: frozenset[Path],
    canonical_delete_remote_keys: frozenset[str],
    cleanup_started: bool,
    require_exact_targets: bool,
) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    media_root = get_settings().media_dir.expanduser().resolve()
    expected_local = frozenset(plan.new_local_path.relative_to(media_root).as_posix() for plan in plans)
    actual_local = _actual_local_keys(media_root)
    canonical_delete_local_keys = frozenset(
        path.relative_to(media_root).as_posix() for path in canonical_delete_local_paths
    )
    expected_local_before_cleanup = expected_local | canonical_delete_local_keys
    registered_local: set[str] = set()
    registered_remote: set[str] = set()
    for asset in session.scalars(select(Asset).order_by(Asset.id.asc())).all():
        identity = identity_from_asset(asset)
        current_scope = normalize_scope(str(asset.scope))
        current_local_path = build_local_path(identity, current_scope)
        if Path(asset.storage_path).expanduser().resolve() != current_local_path:
            raise RuntimeError(f"资源当前本地地址与范围不一致：{asset.id}")
        registered_local.add(current_local_path.relative_to(media_root).as_posix())
        if asset.remote_object_key:
            current_remote_key = build_remote_object_key(identity, current_scope)
            if str(asset.remote_object_key) != current_remote_key:
                raise RuntimeError(f"资源当前 OSS Key 与范围不一致：{asset.id}")
            registered_remote.add(current_remote_key)
    local_sets_match = (
        actual_local == expected_local_before_cleanup
        if require_exact_targets and not cleanup_started
        else expected_local.issubset(actual_local)
        and actual_local.issubset(expected_local_before_cleanup | registered_local)
    )
    if not local_sets_match:
        raise RuntimeError(
            f"本地资源集合不一致：missing={sorted(expected_local - actual_local)} extra={sorted(actual_local - expected_local)}"
        )
    for plan in plans:
        if (
            not plan.new_local_path.is_file()
            or plan.new_local_path.stat().st_size != plan.byte_size
            or _file_sha256(plan.new_local_path) != plan.sha256
        ):
            raise RuntimeError(f"目标本地资源摘要校验失败：{plan.asset_id}")
    for path in canonical_delete_local_paths:
        if not path.exists():
            if cleanup_started:
                continue
            raise RuntimeError(f"当前目录残留副本提前消失：{path}")
        plan = _plan_for_canonical_local_copy(path, plans)
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != plan.byte_size
            or _file_sha256(path) != plan.sha256
        ):
            raise RuntimeError(f"当前目录残留副本在清理前发生变化：{path}")

    expected_remote = frozenset(plan.new_remote_object_key for plan in plans if plan.new_remote_object_key is not None)
    if expected_remote and provider is None:
        raise RuntimeError("迁移清单包含 OSS 资源，但 OSS 当前不可用；任何旧文件均未删除")
    if provider is not None:
        actual_remote = frozenset(
            entry.object_key
            for entry in provider.list_objects(prefix="assets/")
            if not (entry.object_key.endswith("/") and entry.content_length == 0)
        )
        expected_remote_before_cleanup = expected_remote | canonical_delete_remote_keys
        remote_sets_match = (
            actual_remote == expected_remote_before_cleanup
            if require_exact_targets and not cleanup_started
            else expected_remote.issubset(actual_remote)
            and actual_remote.issubset(expected_remote_before_cleanup | registered_remote)
        )
        if not remote_sets_match:
            raise RuntimeError(
                f"OSS 资源集合不一致：missing={sorted(expected_remote - actual_remote)} extra={sorted(actual_remote - expected_remote)}"
            )
        for plan in plans:
            if plan.new_remote_object_key is not None:
                _verify_remote_object(provider, object_key=plan.new_remote_object_key, plan=plan)
        for object_key in canonical_delete_remote_keys:
            if _remote_entry(provider, object_key) is None:
                if cleanup_started:
                    continue
                raise RuntimeError(f"OSS 当前目录残留副本提前消失：{object_key}")
            plan = _plan_for_canonical_remote_copy(object_key, plans)
            _verify_remote_object(provider, object_key=object_key, plan=plan)
    else:
        actual_remote = frozenset()

    if collect_registered_references(session, {url: "legacy" for url in old_urls}):
        raise RuntimeError("主数据库仍存在已注册旧资源引用")
    unhandled = scan_unhandled_legacy_references(session, old_urls)
    if unhandled:
        first = unhandled[0]
        raise RuntimeError(f"主数据库仍存在未注册旧资源引用：{first.table}.{first.column}")
    if collect_waline_asset_references(waline_db_path, {url: "legacy" for url in old_urls}):
        raise RuntimeError("Waline 数据库仍存在旧资源引用")

    expected_old_local = frozenset(
        [
            plan.old_local_path.relative_to(media_root).as_posix()
            for plan in plans
            if plan.old_local_source_present and plan.old_local_path != plan.new_local_path
        ]
        + [path.relative_to(media_root).as_posix() for path in legacy_delete_local_paths]
    )
    actual_old_local = _actual_legacy_local_keys(media_root)
    local_legacy_matches = (
        actual_old_local == expected_old_local if not cleanup_started else actual_old_local.issubset(expected_old_local)
    )
    if not local_legacy_matches:
        raise RuntimeError(
            "本地旧资源集合不一致："
            f"missing={sorted(expected_old_local - actual_old_local)} "
            f"extra={sorted(actual_old_local - expected_old_local)}"
        )
    for plan in plans:
        if (
            not plan.old_local_source_present
            or plan.old_local_path == plan.new_local_path
            or not plan.old_local_path.exists()
        ):
            continue
        if (
            plan.old_local_path.is_symlink()
            or not plan.old_local_path.is_file()
            or plan.old_local_path.stat().st_size != plan.byte_size
            or _file_sha256(plan.old_local_path) != plan.sha256
        ):
            raise RuntimeError(f"旧本地资源在清理前发生变化：{plan.asset_id}")

    expected_old_remote = frozenset(
        [
            plan.old_remote_object_key
            for plan in plans
            if plan.old_remote_source_present
            and plan.old_remote_object_key
            and plan.old_remote_object_key != plan.new_remote_object_key
        ]
        + list(legacy_delete_remote_keys)
    )
    if expected_old_remote and provider is None:
        raise RuntimeError("迁移清单包含待清理 OSS 旧资源，但 OSS 当前不可用；任何旧文件均未删除")
    if provider is not None:
        actual_old_remote = frozenset(
            entry.object_key
            for prefix in _LEGACY_REMOTE_PREFIXES
            for entry in provider.list_objects(prefix=prefix)
            if not (entry.object_key.endswith("/") and entry.content_length == 0)
        )
        remote_legacy_matches = (
            actual_old_remote == expected_old_remote
            if not cleanup_started
            else actual_old_remote.issubset(expected_old_remote)
        )
        if not remote_legacy_matches:
            raise RuntimeError(
                "OSS 旧资源集合不一致："
                f"missing={sorted(expected_old_remote - actual_old_remote)} "
                f"extra={sorted(actual_old_remote - expected_old_remote)}"
            )
        for plan in plans:
            old_key = plan.old_remote_object_key
            if (
                plan.old_remote_source_present
                and old_key
                and old_key != plan.new_remote_object_key
                and old_key in actual_old_remote
            ):
                _verify_remote_object(provider, object_key=old_key, plan=plan)

    return expected_local, actual_local, expected_remote, actual_remote


def _cleanup_and_audit(
    session: Session,
    *,
    payload: dict[str, Any],
    plans: list[AssetMigrationPlan],
    old_urls: set[str],
    waline_db_path: Path,
    provider: Any | None,
) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    media_root = get_settings().media_dir.expanduser().resolve()
    legacy_delete_local_paths, legacy_delete_remote_keys = _manifest_legacy_delete_targets(payload, plans)
    canonical_delete_local_paths, canonical_delete_remote_keys = _manifest_canonical_delete_targets(payload, plans)
    cleanup_started = payload.get("cleanup_started") is True
    expected_local, _actual_local, expected_remote, _actual_remote = _audit_prepared_state(
        session,
        plans=plans,
        old_urls=old_urls,
        waline_db_path=waline_db_path,
        provider=provider,
        legacy_delete_local_paths=legacy_delete_local_paths,
        legacy_delete_remote_keys=legacy_delete_remote_keys,
        canonical_delete_local_paths=canonical_delete_local_paths,
        canonical_delete_remote_keys=canonical_delete_remote_keys,
        cleanup_started=cleanup_started,
        require_exact_targets=False,
    )
    if not cleanup_started:
        payload["cleanup_started"] = True
        _write_json_atomic(migration_manifest_path(), payload)

    if provider is not None:
        for plan in plans:
            old_key = plan.old_remote_object_key
            if plan.old_remote_source_present and old_key and old_key != plan.new_remote_object_key:
                provider.delete_object(object_key=old_key)
        for object_key in sorted(legacy_delete_remote_keys):
            provider.delete_object(object_key=object_key)
        for object_key in sorted(canonical_delete_remote_keys):
            plan = _plan_for_canonical_remote_copy(object_key, plans)
            if _remote_entry(provider, object_key) is None:
                continue
            _verify_remote_object(provider, object_key=object_key, plan=plan)
            provider.delete_object(object_key=object_key)
        for entry in provider.list_objects(prefix="assets/"):
            if entry.object_key.endswith("/") and entry.content_length == 0:
                provider.delete_object(object_key=entry.object_key)
        for prefix in _LEGACY_REMOTE_PREFIXES:
            for entry in provider.list_objects(prefix=prefix):
                if entry.object_key.endswith("/") and entry.content_length == 0:
                    provider.delete_object(object_key=entry.object_key)
        legacy_remote = [
            entry.object_key for prefix in _LEGACY_REMOTE_PREFIXES for entry in provider.list_objects(prefix=prefix)
        ]
        if legacy_remote:
            raise RuntimeError(f"OSS 旧目录仍有对象：{legacy_remote[0]}")
        actual_remote = frozenset(
            entry.object_key
            for entry in provider.list_objects(prefix="assets/")
            if not (entry.object_key.endswith("/") and entry.content_length == 0)
        )

    for plan in plans:
        if (
            not plan.old_local_source_present
            or plan.old_local_path == plan.new_local_path
            or not plan.old_local_path.exists()
        ):
            continue
        if plan.old_local_path.is_symlink() or not plan.old_local_path.is_file():
            raise RuntimeError(f"旧本地资源删除目标类型不安全：{plan.asset_id}")
        if plan.old_local_path.stat().st_size != plan.byte_size or _file_sha256(plan.old_local_path) != plan.sha256:
            raise RuntimeError(f"旧本地资源删除目标摘要不一致：{plan.asset_id}")
        plan.old_local_path.unlink()
    for path in sorted(legacy_delete_local_paths, key=str):
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"本地删除队列目标类型不安全：{path}")
        path.unlink()
    for path in sorted(canonical_delete_local_paths, key=str):
        if not path.exists():
            continue
        plan = _plan_for_canonical_local_copy(path, plans)
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != plan.byte_size
            or _file_sha256(path) != plan.sha256
        ):
            raise RuntimeError(f"当前目录残留副本删除目标发生变化：{path}")
        path.unlink()
    _remove_empty_legacy_directories(media_root)
    _remove_empty_asset_directories(media_root)
    remaining_legacy_roots = [
        media_root / root_name for root_name in _LEGACY_LOCAL_ROOTS if (media_root / root_name).exists()
    ]
    if remaining_legacy_roots:
        raise RuntimeError(f"本地旧资源目录未能彻底移除：{remaining_legacy_roots[0]}")

    expected_local, actual_local, expected_remote, actual_remote = _audit_prepared_state(
        session,
        plans=plans,
        old_urls=old_urls,
        waline_db_path=waline_db_path,
        provider=provider,
        legacy_delete_local_paths=legacy_delete_local_paths,
        legacy_delete_remote_keys=legacy_delete_remote_keys,
        canonical_delete_local_paths=canonical_delete_local_paths,
        canonical_delete_remote_keys=canonical_delete_remote_keys,
        cleanup_started=True,
        require_exact_targets=False,
    )
    if _actual_legacy_local_keys(media_root):
        raise RuntimeError("本地旧资源目录清理后仍有文件")
    if provider is not None:
        remaining_legacy_remote = [
            entry.object_key for prefix in _LEGACY_REMOTE_PREFIXES for entry in provider.list_objects(prefix=prefix)
        ]
        if remaining_legacy_remote:
            raise RuntimeError(f"OSS 旧目录清理后仍有对象：{remaining_legacy_remote[0]}")
    remaining_canonical_local = [path for path in canonical_delete_local_paths if path.exists()]
    if remaining_canonical_local:
        raise RuntimeError(f"本地当前目录残留副本未能清理：{remaining_canonical_local[0]}")
    if provider is not None:
        remaining_canonical_remote = [
            object_key for object_key in canonical_delete_remote_keys if _remote_entry(provider, object_key) is not None
        ]
        if remaining_canonical_remote:
            raise RuntimeError(f"OSS 当前目录残留副本未能清理：{remaining_canonical_remote[0]}")

    return expected_local, actual_local, expected_remote, actual_remote


def _manifest_targets_are_committed(payload: dict[str, Any], session: Session) -> bool:
    plans = _trusted_plans_from_manifest_payload(payload)
    assets = {asset.id: asset for asset in session.scalars(select(Asset).order_by(Asset.id.asc())).all()}
    if len(plans) != len(assets):
        raise RuntimeError("资源迁移清单与数据库资源数量不一致")

    queue_tables_empty = all(
        session.query(queue_model).count() == 0
        for queue_model in (
            AssetMirrorQueueItem,
            AssetRemoteUploadQueueItem,
            AssetRemoteDeleteQueueItem,
            AssetLocalDeleteQueueItem,
        )
    )
    target_matches: list[bool] = []
    original_matches: list[bool] = []
    for plan in plans:
        asset = assets.get(plan.asset_id)
        if asset is None:
            raise RuntimeError(f"资源迁移清单包含未知资源：{plan.asset_id}")
        current_remote_key = str(asset.remote_object_key) if asset.remote_object_key else None
        current_sha256 = str(asset.sha256).lower() if asset.sha256 else None
        current_byte_size = int(asset.byte_size) if asset.byte_size is not None else None
        target_matches.append(
            str(asset.resource_key) == plan.new_resource_key
            and asset.public_slug is None
            and str(asset.scope) == plan.scope
            and str(asset.category) == plan.category
            and Path(asset.storage_path).expanduser().resolve() == plan.new_local_path
            and current_sha256 == plan.sha256
            and current_byte_size == plan.byte_size
            and current_remote_key == plan.new_remote_object_key
            and str(asset.storage_provider) == ("bitiful" if plan.new_remote_object_key else "local")
            and str(asset.remote_status) == ("available" if plan.new_remote_object_key else "none")
            and str(asset.mirror_status) == "completed"
        )
        original_matches.append(
            str(asset.resource_key) == plan.old_resource_key
            and (str(asset.public_slug) if asset.public_slug is not None else None) == plan.old_public_slug
            and str(asset.scope) == plan.old_scope
            and str(asset.category) == plan.old_category
            and Path(asset.storage_path).expanduser().resolve() == plan.old_local_path
            and current_sha256 == plan.old_sha256
            and current_byte_size == plan.old_byte_size
            and current_remote_key == plan.old_remote_object_key
            and str(asset.storage_provider) == plan.old_storage_provider
            and str(asset.remote_status) == plan.old_remote_status
            and str(asset.mirror_status) == plan.old_mirror_status
        )

    if all(target_matches) and queue_tables_empty:
        return True
    if all(original_matches):
        return False
    raise RuntimeError("资源迁移数据库处于不完整的混合状态，拒绝继续清理")


def _manifest_report(payload: dict[str, Any]) -> AssetStorageMigrationReport:
    return AssetStorageMigrationReport(
        migrated_asset_count=int(payload.get("migrated_asset_count", 0)),
        rewritten_reference_count=int(payload.get("rewritten_reference_count", 0)),
        local_expected_keys=frozenset(str(item) for item in payload.get("local_expected_keys", [])),
        local_actual_keys=frozenset(str(item) for item in payload.get("local_actual_keys", [])),
        remote_expected_keys=frozenset(str(item) for item in payload.get("remote_expected_keys", [])),
        remote_actual_keys=frozenset(str(item) for item in payload.get("remote_actual_keys", [])),
    )


def _manifest_created_targets(payload: dict[str, Any]) -> tuple[list[Path], list[str]]:
    raw_plans = payload.get("plans")
    if not isinstance(raw_plans, list) or not all(isinstance(raw, dict) for raw in raw_plans):
        raise RuntimeError("资源迁移恢复清单缺少可信的 plans")
    allowed_local: set[Path] = set()
    allowed_remote: set[str] = set()
    for raw in raw_plans:
        try:
            identity = identity_from_resource_key(str(raw["new_resource_key"]))
            scope = normalize_scope(str(raw["scope"]))
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeError("资源迁移恢复清单包含不可信的目标地址") from exc
        expected_local = build_local_path(identity, scope)
        if Path(str(raw.get("new_local_path"))).expanduser().resolve() != expected_local:
            raise RuntimeError("资源迁移恢复清单包含不可信的本地目标")
        allowed_local.add(expected_local)
        remote_key = raw.get("new_remote_object_key")
        if remote_key is not None:
            expected_remote = build_remote_object_key(identity, scope)
            if str(remote_key) != expected_remote:
                raise RuntimeError("资源迁移恢复清单包含不可信的 OSS 目标")
            allowed_remote.add(expected_remote)
    created_local = [Path(str(item)).expanduser().resolve() for item in payload.get("created_local", [])]
    created_remote = [str(item) for item in payload.get("created_remote", [])]
    if not set(created_local).issubset(allowed_local) or not set(created_remote).issubset(allowed_remote):
        raise RuntimeError("资源迁移恢复清单包含不可信的清理目标")
    return created_local, created_remote


def _record_migration_owned_targets(
    plans: list[AssetMigrationPlan],
    provider: Any | None,
    *,
    owned_local: list[Path],
    owned_remote: list[str],
) -> None:
    known_owned_local = set(owned_local)
    known_owned_remote = set(owned_remote)
    for plan in plans:
        if plan.new_local_path.exists():
            if (
                not plan.new_local_path.is_file()
                or plan.new_local_path.stat().st_size != plan.byte_size
                or _file_sha256(plan.new_local_path) != plan.sha256
            ):
                raise RuntimeError(f"目标本地资源内容冲突：{plan.new_local_path}")
        elif plan.new_local_path not in known_owned_local:
            owned_local.append(plan.new_local_path)
            known_owned_local.add(plan.new_local_path)

        target_key = plan.new_remote_object_key
        if target_key is None:
            continue
        if provider is None:
            raise RuntimeError(f"资源需要 OSS 目标，但 OSS 当前不可用：{plan.asset_id}")
        existing = _remote_entry(provider, target_key)
        if existing is not None:
            if existing.content_length != plan.byte_size:
                raise RuntimeError(f"目标 OSS 对象内容冲突：{target_key}")
            _verify_remote_object(provider, object_key=target_key, plan=plan)
        elif target_key not in known_owned_remote:
            owned_remote.append(target_key)
            known_owned_remote.add(target_key)


def _preflight_canonical_target_inventory(
    plans: list[AssetMigrationPlan],
    provider: Any | None,
    *,
    stale_local_copies: frozenset[Path],
    stale_remote_copies: frozenset[str],
) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    expected_local = frozenset(plan.new_local_path.relative_to(media_root).as_posix() for plan in plans)
    expected_local_with_stale = expected_local | frozenset(
        path.relative_to(media_root).as_posix() for path in stale_local_copies
    )
    actual_local = _actual_local_keys(media_root)
    if actual_local != expected_local_with_stale:
        raise RuntimeError(
            f"目标本地资源集合不一致：missing={sorted(expected_local_with_stale - actual_local)} "
            f"extra={sorted(actual_local - expected_local_with_stale)}"
        )
    expected_remote = frozenset(plan.new_remote_object_key for plan in plans if plan.new_remote_object_key)
    if expected_remote and provider is None:
        raise RuntimeError("目标清单包含 OSS 资源，但 OSS 当前不可用")
    if provider is not None:
        actual_remote = frozenset(
            entry.object_key
            for entry in provider.list_objects(prefix="assets/")
            if not (entry.object_key.endswith("/") and entry.content_length == 0)
        )
        expected_remote_with_stale = expected_remote | stale_remote_copies
        if actual_remote != expected_remote_with_stale:
            raise RuntimeError(
                f"目标 OSS 资源集合不一致：missing={sorted(expected_remote_with_stale - actual_remote)} "
                f"extra={sorted(actual_remote - expected_remote_with_stale)}"
            )


def prepare_asset_storage_layout(
    session: Session,
    *,
    waline_db_path: Path,
    provider: Any | None,
    mirror_local_assets_to_oss: bool = True,
) -> AssetStorageMigrationReport:
    _clear_migration_temp_files()
    existing_manifest = _read_manifest()
    if existing_manifest is None and _waline_backup_path().exists():
        if _waline_backup_path().is_symlink() or not _waline_backup_path().is_file():
            raise RuntimeError("发现类型不安全的孤立 Waline 迁移快照，拒绝继续")
        _waline_backup_path().unlink()
    if existing_manifest is not None:
        if _manifest_targets_are_committed(existing_manifest, session):
            plans = _plans_from_manifest(existing_manifest, session)
            created_local, created_remote = _manifest_created_targets(existing_manifest)
            if any(plan.new_remote_object_key is not None for plan in plans) and provider is None:
                raise RuntimeError("迁移恢复需要校验 OSS 目标，但 OSS 当前不可用")
            _prepare_local_targets(plans, provider, created=created_local)
            _prepare_remote_targets(plans, provider, created=created_remote)
            return _manifest_report(existing_manifest)
        if not _waline_backup_path().is_file():
            raise RuntimeError("资源迁移存在未提交清单，但 Waline 恢复快照缺失，拒绝继续")
        _restore_sqlite(_waline_backup_path(), waline_db_path)

    created_local, created_remote = (
        _manifest_created_targets(existing_manifest) if existing_manifest is not None else ([], [])
    )
    downloaded_legacy_sources: list[Path] = []
    try:
        (
            plans,
            replacements,
            old_urls,
            pending_local_deletes,
            pending_remote_deletes,
            stale_local_copies,
            stale_remote_copies,
        ) = _build_plans(
            session,
            waline_db_path=waline_db_path,
            provider=provider,
            downloaded_legacy_sources=downloaded_legacy_sources,
            mirror_local_assets_to_oss=mirror_local_assets_to_oss,
        )
        migration_plans = [plan for plan in plans if plan.old_resource_key != plan.new_resource_key]
        if not _waline_backup_path().exists():
            _snapshot_sqlite(waline_db_path, _waline_backup_path())
        _record_migration_owned_targets(
            plans,
            provider,
            owned_local=created_local,
            owned_remote=created_remote,
        )
        all_created_local = sorted(set(created_local), key=str)
        all_created_remote = sorted(set(created_remote))
        payload: dict[str, Any] = {
            "version": _MANIFEST_VERSION,
            "migration_key": migration_key,
            "plans": [_plan_payload(plan) for plan in plans],
            "old_urls": sorted(old_urls),
            "created_local": [str(path) for path in all_created_local],
            "created_remote": all_created_remote,
            "legacy_delete_local_paths": [str(path) for path in sorted(pending_local_deletes, key=str)],
            "legacy_delete_remote_keys": sorted(pending_remote_deletes),
            "canonical_delete_local_paths": [str(path) for path in sorted(stale_local_copies, key=str)],
            "canonical_delete_remote_keys": sorted(stale_remote_copies),
            "migrated_asset_count": len(migration_plans),
            "rewritten_reference_count": 0,
        }
        _write_json_atomic(migration_manifest_path(), payload)

        _prepare_local_targets(plans, provider, created=created_local)
        _prepare_remote_targets(plans, provider, created=created_remote)
        payload["created_local"] = [str(path) for path in sorted(set(created_local), key=str)]
        payload["created_remote"] = sorted(set(created_remote))
        _write_json_atomic(migration_manifest_path(), payload)
        _preflight_canonical_target_inventory(
            plans,
            provider,
            stale_local_copies=stale_local_copies,
            stale_remote_copies=stale_remote_copies,
        )

        main_rewrites = rewrite_registered_references(session, replacements)
        waline_rewrites = rewrite_waline_asset_references(waline_db_path, replacements)
        plans_by_id = {plan.asset_id: plan for plan in plans}
        for asset in session.scalars(select(Asset).order_by(Asset.id.asc())).all():
            plan = plans_by_id[asset.id]
            asset.resource_key = plan.new_resource_key
            asset.public_slug = None
            asset.scope = plan.scope
            asset.category = plan.category
            asset.storage_path = str(plan.new_local_path)
            asset.sha256 = plan.sha256
            asset.byte_size = plan.byte_size
            asset.remote_object_key = plan.new_remote_object_key
            if plan.new_remote_object_key is not None:
                asset.storage_provider = "bitiful"
                asset.remote_status = "available"
                asset.mirror_status = "completed"
            else:
                asset.storage_provider = "local"
                asset.remote_status = "none"
                asset.mirror_status = "completed"
        for queue_model in (
            AssetMirrorQueueItem,
            AssetRemoteUploadQueueItem,
            AssetRemoteDeleteQueueItem,
            AssetLocalDeleteQueueItem,
        ):
            session.execute(delete(queue_model))
        session.flush()
        media_root = get_settings().media_dir.expanduser().resolve()
        payload["rewritten_reference_count"] = main_rewrites + waline_rewrites
        payload["local_expected_keys"] = sorted(
            plan.new_local_path.relative_to(media_root).as_posix() for plan in plans
        )
        payload["local_actual_keys"] = sorted(_actual_local_keys(media_root))
        payload["remote_expected_keys"] = sorted(
            plan.new_remote_object_key for plan in plans if plan.new_remote_object_key is not None
        )
        payload["remote_actual_keys"] = (
            sorted(entry.object_key for entry in provider.list_objects(prefix="assets/"))
            if provider is not None
            else []
        )
        _write_json_atomic(migration_manifest_path(), payload)
        return _manifest_report(payload)
    except Exception as exc:
        session.rollback()
        cleanup_failures: list[str] = []
        try:
            _restore_sqlite(_waline_backup_path(), waline_db_path)
        except Exception as cleanup_exc:
            cleanup_failures.append(f"Waline 恢复：{cleanup_exc}")
        for path in [*created_local, *downloaded_legacy_sources]:
            try:
                path.unlink(missing_ok=True)
            except Exception as cleanup_exc:
                cleanup_failures.append(f"本地 {path}: {cleanup_exc}")
        if provider is not None:
            for object_key in created_remote:
                try:
                    provider.delete_object(object_key=object_key)
                except Exception as cleanup_exc:
                    cleanup_failures.append(f"OSS {object_key}: {cleanup_exc}")
        media_root = get_settings().media_dir.expanduser().resolve()
        _remove_empty_legacy_directories(media_root)
        _remove_empty_asset_directories(media_root)
        if not cleanup_failures:
            _remove_migration_state_files()
        if cleanup_failures:
            raise RuntimeError(f"{exc}；失败回滚仍有残留：{'；'.join(cleanup_failures)}") from exc
        raise


def finalize_asset_storage_layout(
    session: Session,
    *,
    waline_db_path: Path,
    provider: Any | None,
) -> AssetStorageMigrationReport:
    _clear_migration_temp_files()
    payload = _read_manifest()
    if payload is None:
        raise RuntimeError("资源迁移恢复清单不存在，无法安全执行旧文件清理")
    cleanup_ready = payload.get("ready_for_cleanup") is True
    plans = _plans_from_manifest(
        payload,
        session,
        allow_extra_assets=cleanup_ready,
        allow_current_targets=cleanup_ready,
    )
    old_urls = {str(item) for item in payload.get("old_urls", [])}
    if payload.get("ready_for_cleanup") is not True:
        verify_asset_storage_layout(
            session,
            waline_db_path=waline_db_path,
            provider=provider,
        )
        payload = _read_manifest()
        if payload is None:
            raise RuntimeError("资源迁移恢复清单在清理前消失")
        plans = _plans_from_manifest(
            payload,
            session,
            allow_extra_assets=True,
            allow_current_targets=True,
        )
        old_urls = {str(item) for item in payload.get("old_urls", [])}
    expected_local, actual_local, expected_remote, actual_remote = _cleanup_and_audit(
        session,
        payload=payload,
        plans=plans,
        old_urls=old_urls,
        waline_db_path=waline_db_path,
        provider=provider,
    )
    report = AssetStorageMigrationReport(
        migrated_asset_count=int(payload.get("migrated_asset_count", 0)),
        rewritten_reference_count=int(payload.get("rewritten_reference_count", 0)),
        local_expected_keys=expected_local,
        local_actual_keys=actual_local,
        remote_expected_keys=expected_remote,
        remote_actual_keys=actual_remote,
    )
    _remove_migration_state_files()
    return report


def verify_asset_storage_layout(
    session: Session,
    *,
    waline_db_path: Path,
    provider: Any | None,
) -> AssetStorageMigrationReport:
    _clear_migration_temp_files()
    payload = _read_manifest()
    if payload is None:
        raise RuntimeError("资源迁移恢复清单不存在，无法验证迁移结果")
    plans = _plans_from_manifest(payload, session)
    legacy_delete_local_paths, legacy_delete_remote_keys = _manifest_legacy_delete_targets(payload, plans)
    canonical_delete_local_paths, canonical_delete_remote_keys = _manifest_canonical_delete_targets(payload, plans)
    old_urls = {str(item) for item in payload.get("old_urls", [])}
    expected_local, actual_local, expected_remote, actual_remote = _audit_prepared_state(
        session,
        plans=plans,
        old_urls=old_urls,
        waline_db_path=waline_db_path,
        provider=provider,
        legacy_delete_local_paths=legacy_delete_local_paths,
        legacy_delete_remote_keys=legacy_delete_remote_keys,
        canonical_delete_local_paths=canonical_delete_local_paths,
        canonical_delete_remote_keys=canonical_delete_remote_keys,
        cleanup_started=False,
        require_exact_targets=True,
    )
    payload["ready_for_cleanup"] = True
    payload["cleanup_started"] = False
    payload["local_expected_keys"] = sorted(expected_local)
    payload["local_actual_keys"] = sorted(actual_local)
    payload["remote_expected_keys"] = sorted(expected_remote)
    payload["remote_actual_keys"] = sorted(actual_remote)
    _write_json_atomic(migration_manifest_path(), payload)
    return _manifest_report(payload)


def migrate_asset_storage_layout(
    session: Session,
    *,
    waline_db_path: Path,
    provider: Any | None,
) -> AssetStorageMigrationReport:
    prepare_asset_storage_layout(
        session,
        waline_db_path=waline_db_path,
        provider=provider,
    )
    session.commit()
    verify_asset_storage_layout(
        session,
        waline_db_path=waline_db_path,
        provider=provider,
    )
    return finalize_asset_storage_layout(
        session,
        waline_db_path=waline_db_path,
        provider=provider,
    )


def apply(session: Session) -> None:
    settings = get_settings()
    object_storage_config = get_or_create_object_storage_config(session)
    provider = build_object_storage_maintenance_provider(session)
    prepare_asset_storage_layout(
        session,
        waline_db_path=settings.waline_db_path,
        provider=provider,
        mirror_local_assets_to_oss=bool(object_storage_config.enabled),
    )


def finalize(session: Session) -> None:
    settings = get_settings()
    provider = build_object_storage_maintenance_provider(session)
    verify_asset_storage_layout(
        session,
        waline_db_path=settings.waline_db_path,
        provider=provider,
    )


def cleanup(session: Session) -> None:
    if _read_manifest() is None:
        return
    settings = get_settings()
    provider = build_object_storage_maintenance_provider(session)
    finalize_asset_storage_layout(
        session,
        waline_db_path=settings.waline_db_path,
        provider=provider,
    )


def cleanup_pending() -> bool:
    return migration_manifest_path().is_file()


def rollback_external(session: Session) -> None:
    _clear_migration_temp_files()
    payload = _read_manifest()
    if payload is None:
        return
    if payload.get("cleanup_started") is True:
        raise RuntimeError("资源旧副本清理已经开始，不能再自动回滚到旧版本")
    plans = _trusted_plans_from_manifest_payload(payload)
    _created_local, created_remote = _manifest_created_targets(payload)
    if not created_remote:
        return
    provider = build_object_storage_maintenance_provider(session)
    if provider is None:
        raise RuntimeError("无法验证 OSS 旧副本，拒绝执行升级回滚清理")

    plans_by_target = {plan.new_remote_object_key: plan for plan in plans if plan.new_remote_object_key is not None}
    for plan in plans:
        old_key = plan.old_remote_object_key
        if not plan.old_remote_source_present or not old_key or old_key == plan.new_remote_object_key:
            continue
        if _remote_entry(provider, old_key) is None:
            raise RuntimeError(f"升级回滚所需的 OSS 旧对象不存在：{old_key}")
        _verify_remote_object(provider, object_key=old_key, plan=plan)

    for target_key in created_remote:
        plan = plans_by_target.get(target_key)
        if plan is None:
            raise RuntimeError(f"升级回滚清理目标不属于迁移计划：{target_key}")
        if _remote_entry(provider, target_key) is None:
            continue
        _verify_remote_object(provider, object_key=target_key, plan=plan)
        provider.delete_object(object_key=target_key)
