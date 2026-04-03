from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Protocol

import zstandard as zstd
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy.orm import Session

from aerisun.core.base import uuid_str
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.ops import repository as repo
from aerisun.domain.ops.schemas import (
    BackupCommitRead,
    BackupCredentialAcknowledgeWrite,
    BackupCredentialEnsureRead,
    BackupCredentialExportRead,
    BackupCredentialExportWrite,
    BackupQueueItemRead,
    BackupRunRead,
    BackupSnapshotRead,
    BackupSyncConfig,
    BackupSyncConfigTestRead,
    BackupSyncConfigUpdate,
    BackupTransportConfig,
)

CHUNK_SIZE_BYTES = 8 * 1024 * 1024
BACKUP_JOB_NAME = "backup_sync"
CHUNK_DIGEST_ALGORITHM = "sha256"
MANIFEST_VERSION = 1

_restore_lock = threading.Lock()
_restore_in_progress = threading.Event()

_SFTP_UNSAFE_RE = re.compile(r"[\n\r]")

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BackupCredentialBundle:
    credential_ref: str
    secrets_private_key: x25519.X25519PrivateKey
    secrets_public_key: x25519.X25519PublicKey
    secrets_fingerprint: str


@dataclass(slots=True)
class PreparedChunk:
    digest: str
    size: int
    temp_path: Path


@dataclass(slots=True)
class PreparedFile:
    relative_path: str
    temp_path: Path
    size: int
    digest: str
    chunks: list[PreparedChunk]
    dataset_kind: str
    compression: str | None = None
    encryption: dict[str, Any] | None = None


@dataclass(slots=True)
class PreparedRunArtifacts:
    temp_dir: Path
    files: list[PreparedFile]
    dataset_versions: dict[str, Any]


class BackupTransport(Protocol):
    def begin_session(self) -> dict[str, Any]: ...

    def has_chunk(self, digest: str) -> bool: ...

    def upload_chunk(self, digest: str, chunk_path: Path) -> None: ...

    def upload_manifest(self, digest: str, payload: bytes) -> None: ...

    def commit(self, *, commit_id: str, manifest_digest: str, manifest: dict[str, Any]) -> dict[str, Any]: ...

    def list_commits(self) -> list[dict[str, Any]]: ...

    def fetch_commit(self, commit_id: str) -> dict[str, Any]: ...

    def fetch_manifest(self, digest: str) -> dict[str, Any]: ...

    def read_chunk(self, digest: str) -> bytes: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_pem_bytes(path: Path) -> bytes:
    if not path.exists():
        raise ValidationError(f"Backup credential file not found: {path}")
    return path.read_bytes()


def _fingerprint_public_key(raw_public_bytes: bytes) -> str:
    return hashlib.sha256(raw_public_bytes).hexdigest()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def load_backup_credentials(credential_ref: str) -> BackupCredentialBundle:
    secrets_private = serialization.load_pem_private_key(
        _load_pem_bytes(_current_private_key_path(credential_ref)), password=None
    )
    secrets_public = serialization.load_pem_public_key(_load_pem_bytes(_current_public_key_path(credential_ref)))
    if not isinstance(secrets_private, x25519.X25519PrivateKey):
        raise ValidationError("Backup secrets private key must be an X25519 key")
    if not isinstance(secrets_public, x25519.X25519PublicKey):
        raise ValidationError("Backup secrets public key must be an X25519 key")

    return BackupCredentialBundle(
        credential_ref=credential_ref,
        secrets_private_key=secrets_private,
        secrets_public_key=secrets_public,
        secrets_fingerprint=_fingerprint_public_key(secrets_public.public_bytes_raw()),
    )


def _credential_dir(credential_ref: str) -> Path:
    return get_settings().secrets_dir / "backup-sync" / credential_ref


def _current_private_key_path(credential_ref: str) -> Path:
    return _credential_dir(credential_ref) / "secrets_x25519.pem"


def _current_public_key_path(credential_ref: str) -> Path:
    return _credential_dir(credential_ref) / "secrets_x25519.pub.pem"


def _archive_dir(credential_ref: str) -> Path:
    return _credential_dir(credential_ref) / "archived"


def _archive_key_dir(credential_ref: str, fingerprint: str) -> Path:
    return _archive_dir(credential_ref) / fingerprint


def _archive_private_key_path(credential_ref: str, fingerprint: str) -> Path:
    return _archive_key_dir(credential_ref, fingerprint) / "secrets_x25519.pem"


def _archive_public_key_path(credential_ref: str, fingerprint: str) -> Path:
    return _archive_key_dir(credential_ref, fingerprint) / "secrets_x25519.pub.pem"


def _list_archived_fingerprints(credential_ref: str) -> list[str]:
    archive_root = _archive_dir(credential_ref)
    if not archive_root.exists():
        return []
    return sorted(path.name for path in archive_root.iterdir() if path.is_dir())


def _derive_passphrase_key(passphrase: str, *, salt: bytes) -> bytes:
    if len(passphrase) < 8:
        raise ValidationError("Recovery key password must be at least 8 characters")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def _encrypt_private_key_for_escrow(private_key_pem: bytes, *, passphrase: str) -> dict[str, Any]:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_passphrase_key(passphrase, salt=salt)
    ciphertext = AESGCM(key).encrypt(nonce, private_key_pem, None)
    return {
        "version": 1,
        "scheme": "passphrase-aesgcm",
        "kdf": "scrypt",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def _decrypt_private_key_from_escrow(payload: dict[str, Any], *, passphrase: str) -> bytes:
    if payload.get("scheme") != "passphrase-aesgcm":
        raise ValidationError("Unsupported recovery key escrow scheme")
    key = _derive_passphrase_key(passphrase, salt=base64.b64decode(payload["salt"]))
    return AESGCM(key).decrypt(
        base64.b64decode(payload["nonce"]),
        base64.b64decode(payload["ciphertext"]),
        None,
    )


def ensure_backup_credentials(
    *, credential_ref: str, site_slug: str, force: bool = False
) -> BackupCredentialEnsureRead:
    normalized_ref = credential_ref.strip()
    if not normalized_ref:
        raise ValidationError("Backup credential_ref is required")
    normalized_site_slug = site_slug.strip() or get_settings().backup_sync_default_site_slug
    key_dir = _credential_dir(normalized_ref)
    key_paths = {
        "secrets_x25519.pem": _current_private_key_path(normalized_ref),
        "secrets_x25519.pub.pem": _current_public_key_path(normalized_ref),
    }
    existing = {name: path.exists() for name, path in key_paths.items()}
    created = False

    if all(existing.values()) and not force:
        bundle = load_backup_credentials(normalized_ref)
    else:
        if any(existing.values()) and not force:
            raise ValidationError(
                f"Backup credential directory is incomplete: {key_dir}. Delete it or regenerate with force."
            )
        secrets_private = x25519.X25519PrivateKey.generate()
        secrets_public = secrets_private.public_key()
        key_dir.mkdir(parents=True, exist_ok=True)
        key_paths["secrets_x25519.pem"].write_bytes(
            secrets_private.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        os.chmod(key_paths["secrets_x25519.pem"], 0o600)
        key_paths["secrets_x25519.pub.pem"].write_bytes(
            secrets_public.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        os.chmod(key_paths["secrets_x25519.pub.pem"], 0o644)
        bundle = load_backup_credentials(normalized_ref)
        created = True

    return BackupCredentialEnsureRead(
        credential_ref=normalized_ref,
        site_slug=normalized_site_slug,
        credential_dir=str(key_dir),
        secrets_fingerprint=bundle.secrets_fingerprint,
        created=created,
        archived_fingerprints=_list_archived_fingerprints(normalized_ref),
    )


def _write_runtime_keypair(
    credential_ref: str,
    *,
    private_key: x25519.X25519PrivateKey,
    public_key: x25519.X25519PublicKey,
) -> str:
    key_dir = _credential_dir(credential_ref)
    key_dir.mkdir(parents=True, exist_ok=True)
    private_path = _current_private_key_path(credential_ref)
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    os.chmod(private_path, 0o600)
    public_path = _current_public_key_path(credential_ref)
    public_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    os.chmod(public_path, 0o644)
    return _fingerprint_public_key(public_key.public_bytes_raw())


def _archive_current_runtime_keypair(credential_ref: str) -> str | None:
    private_path = _current_private_key_path(credential_ref)
    public_path = _current_public_key_path(credential_ref)
    if not private_path.exists() or not public_path.exists():
        return None
    public_key = serialization.load_pem_public_key(public_path.read_bytes())
    if not isinstance(public_key, x25519.X25519PublicKey):
        raise ValidationError("Backup secrets public key must be an X25519 key")
    fingerprint = _fingerprint_public_key(public_key.public_bytes_raw())
    archive_key_dir = _archive_key_dir(credential_ref, fingerprint)
    archive_key_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(private_path, _archive_private_key_path(credential_ref, fingerprint))
    shutil.copy2(public_path, _archive_public_key_path(credential_ref, fingerprint))
    return fingerprint


def _iter_runtime_key_material(credential_ref: str) -> list[tuple[str, str, bytes, str]]:
    items: list[tuple[str, str, bytes, str]] = []
    current_private = _current_private_key_path(credential_ref)
    current_public = _current_public_key_path(credential_ref)
    if current_private.exists() and current_public.exists():
        public_pem = current_public.read_text(encoding="utf-8")
        public_key = serialization.load_pem_public_key(current_public.read_bytes())
        if isinstance(public_key, x25519.X25519PublicKey):
            fingerprint = _fingerprint_public_key(public_key.public_bytes_raw())
            items.append(("active", fingerprint, current_private.read_bytes(), public_pem))
    for fingerprint in _list_archived_fingerprints(credential_ref):
        archive_private = _archive_private_key_path(credential_ref, fingerprint)
        archive_public = _archive_public_key_path(credential_ref, fingerprint)
        if not archive_private.exists() or not archive_public.exists():
            continue
        items.append(
            ("archived", fingerprint, archive_private.read_bytes(), archive_public.read_text(encoding="utf-8"))
        )
    return items


def _sync_recovery_keyring_to_db(
    session: Session,
    *,
    credential_ref: str,
    site_slug: str,
    passphrase: str,
) -> BackupCredentialEnsureRead:
    items = _iter_runtime_key_material(credential_ref)
    active_fingerprint: str | None = None
    archived_fingerprints: list[str] = []
    for status, fingerprint, private_pem, public_pem in items:
        payload = _encrypt_private_key_for_escrow(private_pem, passphrase=passphrase)
        row = repo.get_backup_recovery_key_by_fingerprint(
            session, credential_ref=credential_ref, secrets_fingerprint=fingerprint
        )
        if row is None:
            row = repo.create_backup_recovery_key(
                session,
                credential_ref=credential_ref,
                site_slug=site_slug,
                status=status,
                secrets_fingerprint=fingerprint,
                secrets_public_pem=public_pem,
                encrypted_private_payload=payload,
                archived_at=_utcnow() if status == "archived" else None,
                last_exported_at=_utcnow(),
                acknowledged_at=None if status == "active" else _utcnow(),
            )
        else:
            row.site_slug = site_slug
            row.status = status
            row.secrets_public_pem = public_pem
            row.encrypted_private_payload = payload
            row.archived_at = _utcnow() if status == "archived" else None
            row.last_exported_at = _utcnow()
            row.acknowledged_at = None if status == "active" else (row.acknowledged_at or _utcnow())
        if status == "active":
            active_fingerprint = fingerprint
        else:
            archived_fingerprints.append(fingerprint)
    session.commit()
    return BackupCredentialEnsureRead(
        credential_ref=credential_ref,
        site_slug=site_slug,
        credential_dir=str(_credential_dir(credential_ref)),
        secrets_fingerprint=active_fingerprint or "",
        created=False,
        archived_fingerprints=sorted(archived_fingerprints),
    )


def issue_backup_recovery_key(
    session: Session,
    payload: BackupCredentialExportWrite,
) -> BackupCredentialExportRead:
    credential_ref = payload.credential_ref.strip() or "aerisun-backup-source"
    site_slug = payload.site_slug.strip() or get_settings().backup_sync_default_site_slug
    current_private = _current_private_key_path(credential_ref)
    current_public = _current_public_key_path(credential_ref)
    has_current = current_private.exists() and current_public.exists()

    if has_current and payload.rotate:
        _archive_current_runtime_keypair(credential_ref)
        new_private = x25519.X25519PrivateKey.generate()
        new_public = new_private.public_key()
        _write_runtime_keypair(credential_ref, private_key=new_private, public_key=new_public)
    elif not has_current:
        new_private = x25519.X25519PrivateKey.generate()
        new_public = new_private.public_key()
        _write_runtime_keypair(credential_ref, private_key=new_private, public_key=new_public)

    status = _sync_recovery_keyring_to_db(
        session,
        credential_ref=credential_ref,
        site_slug=site_slug,
        passphrase=payload.passphrase,
    )
    private_key_pem = _current_private_key_path(credential_ref).read_text(encoding="utf-8")
    return BackupCredentialExportRead(
        credential_ref=credential_ref,
        site_slug=site_slug,
        credential_dir=status.credential_dir,
        secrets_fingerprint=status.secrets_fingerprint,
        archived_fingerprints=status.archived_fingerprints,
        rotated=bool(payload.rotate),
        filename=f"{credential_ref}-{status.secrets_fingerprint[:12]}.pem",
        private_key_pem=private_key_pem,
    )


def acknowledge_backup_recovery_key(
    session: Session, payload: BackupCredentialAcknowledgeWrite
) -> BackupCredentialEnsureRead:
    credential_ref = payload.credential_ref.strip() or "aerisun-backup-source"
    active = repo.get_active_backup_recovery_key(session, credential_ref=credential_ref)
    if active is None:
        raise ResourceNotFound("Backup recovery key not found")
    active.acknowledged_at = _utcnow()
    session.commit()
    return ensure_backup_credentials(
        credential_ref=credential_ref,
        site_slug=active.site_slug,
        force=False,
    )


def _build_transport_config(config) -> BackupTransportConfig:
    return BackupTransportConfig(
        mode=config.transport_mode,
        remote_host=config.remote_host,
        remote_port=config.remote_port,
        remote_path=config.remote_path,
        remote_username=config.remote_username,
    )


def _recovery_key_status(session: Session, *, credential_ref: str | None) -> tuple[bool, bool, str | None, int]:
    if not credential_ref:
        return False, False, None, 0
    active = repo.get_active_backup_recovery_key(session, credential_ref=credential_ref)
    items = repo.list_backup_recovery_keys(session, credential_ref=credential_ref)
    archived_count = sum(1 for item in items if item.status == "archived")
    return (
        active is not None,
        bool(active is not None and active.acknowledged_at is not None),
        active.secrets_fingerprint if active is not None else None,
        archived_count,
    )


def _config_read(config) -> BackupSyncConfig:
    session_factory = get_session_factory()
    with session_factory() as session:
        recovery_ready, recovery_acknowledged, active_fingerprint, archived_count = _recovery_key_status(
            session, credential_ref=config.credential_ref
        )
    return BackupSyncConfig(
        id=config.id,
        enabled=config.enabled,
        paused=config.paused,
        interval_minutes=config.interval_minutes,
        transport_mode=config.transport_mode,
        site_slug=config.site_slug,
        credential_ref=config.credential_ref,
        encrypt_runtime_data=config.encrypt_runtime_data,
        max_retries=config.max_retries,
        retry_backoff_seconds=config.retry_backoff_seconds,
        max_retention_count=config.max_retention_count,
        last_scheduled_at=config.last_scheduled_at,
        last_synced_at=config.last_synced_at,
        last_error=config.last_error,
        recovery_key_ready=recovery_ready,
        recovery_key_acknowledged=recovery_acknowledged,
        active_recovery_key_fingerprint=active_fingerprint,
        archived_recovery_key_count=archived_count,
        transport=_build_transport_config(config),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _queue_item_read(item) -> BackupQueueItemRead:
    return BackupQueueItemRead.model_validate(item)


def _run_read(item) -> BackupRunRead:
    return BackupRunRead.model_validate(item)


def _commit_read(item) -> BackupCommitRead:
    return BackupCommitRead.model_validate(item)


def _to_snapshot(commit) -> BackupSnapshotRead:
    completed_at = commit.snapshot_finished_at or commit.created_at
    return BackupSnapshotRead(
        id=commit.id,
        snapshot_type=commit.trigger_kind,
        status="completed",
        db_path=commit.datasets.get("aerisun_db", {}).get("target_path", "aerisun.db"),
        replica_url=None,
        backup_path=commit.backup_path,
        checksum=commit.manifest_digest,
        completed_at=completed_at,
        created_at=commit.created_at,
        updated_at=commit.updated_at,
    )


def _config_object_from_payload(payload: BackupSyncConfigUpdate):
    settings = get_settings()
    return SimpleNamespace(
        transport_mode="sftp",
        site_slug=payload.site_slug.strip() or settings.backup_sync_default_site_slug,
        remote_host=payload.remote_host,
        remote_port=payload.remote_port or 22,
        remote_path=payload.remote_path,
        remote_username=payload.remote_username,
        credential_ref=payload.credential_ref or "aerisun-backup-source",
        encrypt_runtime_data=bool(payload.encrypt_runtime_data),
        enabled=bool(payload.enabled),
        paused=bool(payload.paused),
        interval_minutes=max(int(payload.interval_minutes or settings.backup_sync_default_interval_minutes), 1),
        max_retries=max(int(payload.max_retries or 0), 0),
        retry_backoff_seconds=max(int(payload.retry_backoff_seconds or 300), 30),
        max_retention_count=max(int(payload.max_retention_count or 0), 0),
    )


def get_or_create_backup_sync_config(session: Session):
    settings = get_settings()
    config = repo.get_backup_target_config(session)
    if config is None:
        config = repo.create_backup_target_config(
            session,
            enabled=False,
            paused=False,
            interval_minutes=settings.backup_sync_default_interval_minutes,
            transport_mode="sftp",
            site_slug=settings.backup_sync_default_site_slug,
            remote_port=22,
            credential_ref="aerisun-backup-source",
            max_retries=3,
            retry_backoff_seconds=300,
        )
        session.commit()
        session.refresh(config)
    return config


def get_backup_sync_config(session: Session) -> BackupSyncConfig:
    return _config_read(get_or_create_backup_sync_config(session))


def test_backup_sync_config(session: Session, payload: BackupSyncConfigUpdate) -> BackupSyncConfigTestRead:
    config = _config_object_from_payload(payload)
    _validate_config(config)
    recovery_ready, recovery_acknowledged, _, _ = _recovery_key_status(session, credential_ref=config.credential_ref)
    transport = SftpTransport(
        host=config.remote_host,
        port=config.remote_port or 22,
        username=config.remote_username,
        remote_root=config.remote_path,
        site_slug=config.site_slug,
    )
    started_at = time.perf_counter()
    try:
        transport.begin_session()
        transport.probe_write_access()
    except ValidationError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return BackupSyncConfigTestRead(
            ok=False,
            summary=str(exc),
            latency_ms=latency_ms,
            remote_path_preview=str(config.remote_path or ""),
            recovery_key_ready=recovery_ready,
            recovery_key_acknowledged=recovery_acknowledged,
        )
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return BackupSyncConfigTestRead(
        ok=True,
        summary="SFTP 连接正常，远端目录可写。",
        latency_ms=latency_ms,
        remote_path_preview=str(config.remote_path or ""),
        recovery_key_ready=recovery_ready,
        recovery_key_acknowledged=recovery_acknowledged,
    )


def update_backup_sync_config(session: Session, payload: BackupSyncConfigUpdate) -> BackupSyncConfig:
    from aerisun.domain.automation.events import emit_backup_config_updated

    config = get_or_create_backup_sync_config(session)
    requested_transport_mode = str(payload.transport_mode or "sftp").strip().lower()
    if requested_transport_mode != "sftp":
        raise ValidationError("Backup transport mode must be sftp")
    config.enabled = payload.enabled
    config.paused = payload.paused
    config.interval_minutes = max(payload.interval_minutes, 1)
    config.transport_mode = "sftp"
    config.site_slug = payload.site_slug.strip() or get_settings().backup_sync_default_site_slug
    config.remote_host = payload.remote_host
    config.remote_port = payload.remote_port
    config.remote_path = payload.remote_path
    config.remote_username = payload.remote_username
    config.credential_ref = payload.credential_ref
    config.encrypt_runtime_data = bool(payload.encrypt_runtime_data)
    config.max_retries = max(payload.max_retries, 0)
    config.retry_backoff_seconds = max(payload.retry_backoff_seconds, 30)
    config.max_retention_count = max(payload.max_retention_count, 0)
    _validate_config(config)
    active_recovery_key = repo.get_active_backup_recovery_key(session, credential_ref=str(config.credential_ref))
    if active_recovery_key is None:
        raise ValidationError("请先获取恢复私钥并妥善保存，然后再保存备份配置。")
    if active_recovery_key.acknowledged_at is None:
        raise ValidationError("请先复制或下载恢复私钥，然后再保存备份配置。")
    session.commit()
    session.refresh(config)
    emit_backup_config_updated(
        session,
        config_id=config.id,
        enabled=bool(config.enabled),
        paused=bool(config.paused),
        transport_mode=config.transport_mode,
        interval_minutes=int(config.interval_minutes),
    )
    return _config_read(config)


def pause_backup_sync(session: Session) -> BackupSyncConfig:
    config = get_or_create_backup_sync_config(session)
    config.paused = True
    session.commit()
    session.refresh(config)
    return _config_read(config)


def resume_backup_sync(session: Session) -> BackupSyncConfig:
    config = get_or_create_backup_sync_config(session)
    config.paused = False
    session.commit()
    session.refresh(config)
    return _config_read(config)


def list_backup_sync_queue(session: Session) -> list[BackupQueueItemRead]:
    return [_queue_item_read(item) for item in repo.list_backup_queue_items(session)]


def list_backup_sync_runs(session: Session) -> list[BackupRunRead]:
    return [_run_read(item) for item in repo.list_sync_runs(session)]


def list_backup_sync_commits(session: Session) -> list[BackupCommitRead]:
    return [_commit_read(item) for item in repo.list_backup_commits(session)]


def list_backup_snapshots(session: Session) -> list[BackupSnapshotRead]:
    return [_to_snapshot(item) for item in repo.list_backup_commits(session)]


def _validate_config(config) -> None:
    if config.transport_mode != "sftp":
        raise ValidationError("Backup transport mode must be sftp")
    if not config.credential_ref:
        raise ValidationError("Backup credential_ref is required")
    if not config.remote_host or not config.remote_path or not config.remote_username:
        raise ValidationError("SFTP transport requires remote_host, remote_path, and remote_username")


def collect_dataset_versions() -> dict[str, Any]:
    settings = get_settings()
    automation_packs_root = settings.data_dir / "automation" / "packs"

    def _path_info(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"exists": False}
        stat = path.stat()
        return {
            "exists": True,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }

    media_files = sorted(
        str(path.relative_to(settings.media_dir)) for path in settings.media_dir.rglob("*") if path.is_file()
    )
    secret_files = sorted(
        str(path.relative_to(settings.secrets_dir))
        for path in settings.secrets_dir.rglob("*")
        if path.is_file() and "backup-sync/" not in str(path.relative_to(settings.secrets_dir)).replace("\\", "/")
    )
    automation_pack_files = (
        sorted(
            str(path.relative_to(automation_packs_root)) for path in automation_packs_root.rglob("*") if path.is_file()
        )
        if automation_packs_root.exists()
        else []
    )
    return {
        "aerisun_db": _path_info(settings.db_path),
        "waline_db": _path_info(settings.waline_db_path),
        "workflow_db": _path_info(settings.workflow_db_path),
        "media": {
            "file_count": len(media_files),
            "paths_digest": _sha256_bytes("\n".join(media_files).encode("utf-8")),
        },
        "secrets": {
            "file_count": len(secret_files),
            "paths_digest": _sha256_bytes("\n".join(secret_files).encode("utf-8")),
        },
        "automation_packs": {
            "file_count": len(automation_pack_files),
            "paths_digest": _sha256_bytes("\n".join(automation_pack_files).encode("utf-8")),
        },
    }


def ensure_backup_queue_item(session: Session, *, trigger_kind: str, force: bool = False):
    from aerisun.domain.automation.events import emit_backup_sync_triggered

    config = get_or_create_backup_sync_config(session)
    _validate_config(config)
    existing = repo.find_active_backup_queue_item(session)
    if existing is not None and not force:
        return existing

    item = repo.create_backup_queue_item(
        session,
        transport=config.transport_mode,
        trigger_kind=trigger_kind,
        status="queued",
        dataset_versions=collect_dataset_versions(),
        verified_chunks=[],
        retry_count=0,
        next_retry_at=_utcnow(),
    )
    config.last_scheduled_at = _utcnow()
    session.commit()
    session.refresh(item)
    emit_backup_sync_triggered(
        session,
        queue_item_id=item.id,
        trigger_kind=item.trigger_kind,
        transport=item.transport,
    )
    return item


def trigger_backup_sync(session: Session) -> BackupRunRead:
    queue_item = ensure_backup_queue_item(session, trigger_kind="manual", force=False)
    dispatch_backup_sync()
    session.expire_all()
    refreshed = repo.get_backup_queue_item(session, queue_item.id)
    run = next(
        (item for item in repo.list_sync_runs(session) if item.queue_item_id == queue_item.id),
        None,
    )
    if run is None:
        raise StateConflict("Backup sync run was not created")
    if refreshed is not None:
        session.refresh(run)
    return _run_read(run)


def retry_backup_sync_run(session: Session, run_id: str) -> BackupRunRead:
    from aerisun.domain.automation.events import emit_backup_sync_retried

    run = repo.get_sync_run(session, run_id)
    if run is None:
        raise ResourceNotFound("Backup sync run not found")
    if run.queue_item_id is None:
        raise ValidationError("Backup sync run has no queue item to retry")
    queue_item = repo.get_backup_queue_item(session, run.queue_item_id)
    if queue_item is None:
        raise ResourceNotFound("Backup queue item not found")
    queue_item.status = "retrying"
    queue_item.next_retry_at = _utcnow()
    queue_item.last_error = None
    session.commit()
    emit_backup_sync_retried(
        session,
        run_id=run.id,
        queue_item_id=queue_item.id,
        retry_count=int(queue_item.retry_count),
    )
    dispatch_backup_sync()
    session.refresh(run)
    return _run_read(run)


def dispatch_backup_sync() -> BackupRunRead | None:
    from aerisun.domain.automation.events import emit_backup_sync_started

    if _restore_in_progress.is_set():
        logger.info("Skipping backup dispatch: restore in progress")
        return None

    session_factory = get_session_factory()
    now = _utcnow()
    with session_factory() as session:
        config = get_or_create_backup_sync_config(session)
        if config.enabled and not config.paused:
            last_reference = _as_utc(config.last_scheduled_at or config.last_synced_at or config.created_at)
            if (
                last_reference is None or now >= last_reference + timedelta(minutes=config.interval_minutes)
            ) and repo.find_active_backup_queue_item(session) is None:
                ensure_backup_queue_item(session, trigger_kind="scheduled")
                config = get_or_create_backup_sync_config(session)
        if repo.find_running_sync_run(session, job_name=BACKUP_JOB_NAME) is not None:
            return None
        queue_item = repo.find_due_backup_queue_item(session, now=now)
        if queue_item is None:
            return None
        run = repo.create_sync_run(
            session,
            job_name=BACKUP_JOB_NAME,
            status="running",
            transport=queue_item.transport,
            trigger_kind=queue_item.trigger_kind,
            queue_item_id=queue_item.id,
            started_at=now,
            stats_json={},
            retry_count=queue_item.retry_count,
        )
        queue_item.status = "running"
        queue_item.started_at = now
        session.commit()
        session.refresh(run)
        run_id = run.id
        queue_item_id = queue_item.id
        emit_backup_sync_started(
            session,
            run_id=run.id,
            queue_item_id=queue_item.id,
            trigger_kind=run.trigger_kind,
            transport=run.transport,
        )

    try:
        _execute_run(run_id=run_id, queue_item_id=queue_item_id)
    except Exception as exc:
        _mark_run_failed(run_id=run_id, queue_item_id=queue_item_id, error=str(exc))
    with session_factory() as session:
        run = repo.get_sync_run(session, run_id)
        return _run_read(run) if run is not None else None


def _mark_run_failed(*, run_id: str, queue_item_id: str, error: str) -> None:
    from aerisun.domain.automation.events import emit_backup_sync_failed

    session_factory = get_session_factory()
    with session_factory() as session:
        config = get_or_create_backup_sync_config(session)
        run = repo.get_sync_run(session, run_id)
        queue_item = repo.get_backup_queue_item(session, queue_item_id)
        now = _utcnow()
        if queue_item is not None:
            queue_item.retry_count += 1
            queue_item.last_error = error
            queue_item.finished_at = now
            if queue_item.retry_count > config.max_retries:
                queue_item.status = "failed"
                queue_item.next_retry_at = None
            else:
                queue_item.status = "retrying"
                queue_item.next_retry_at = now + timedelta(
                    seconds=config.retry_backoff_seconds * queue_item.retry_count
                )
        if run is not None:
            run.status = "failed"
            run.finished_at = now
            run.last_error = error
            run.next_retry_at = queue_item.next_retry_at if queue_item is not None else None
            run.message = error
        config.last_error = error
        session.commit()
        if run is not None:
            emit_backup_sync_failed(
                session,
                run_id=run.id,
                queue_item_id=queue_item.id if queue_item is not None else None,
                error=error,
                retry_count=int(queue_item.retry_count if queue_item is not None else 0),
            )


def _mark_run_completed(
    *,
    run_id: str,
    queue_item_id: str,
    commit_id: str,
    stats_json: dict[str, Any],
) -> None:
    from aerisun.domain.automation.events import emit_backup_sync_completed

    session_factory = get_session_factory()
    with session_factory() as session:
        config = get_or_create_backup_sync_config(session)
        run = repo.get_sync_run(session, run_id)
        queue_item = repo.get_backup_queue_item(session, queue_item_id)
        now = _utcnow()
        if queue_item is not None:
            queue_item.status = "completed"
            queue_item.finished_at = now
            queue_item.next_retry_at = None
            queue_item.last_error = None
        if run is not None:
            run.status = "completed"
            run.finished_at = now
            run.commit_id = commit_id
            run.stats_json = stats_json
            run.message = "Backup sync completed"
            run.last_error = None
        config.last_synced_at = now
        config.last_error = None
        session.commit()
        if run is not None:
            emit_backup_sync_completed(
                session,
                run_id=run.id,
                queue_item_id=queue_item.id if queue_item is not None else None,
                commit_id=commit_id,
                stats=stats_json,
            )


def _enforce_retention(config, transport: BackupTransport) -> None:
    """Delete oldest backup commits that exceed max_retention_count."""
    max_count = getattr(config, "max_retention_count", 0)
    if not max_count or max_count <= 0:
        return
    session_factory = get_session_factory()
    with session_factory() as session:
        all_commits = repo.list_backup_commits(session)
        if len(all_commits) <= max_count:
            return
        to_remove = all_commits[max_count:]
        for commit in to_remove:
            if hasattr(transport, "delete_commit"):
                try:
                    transport.delete_commit(commit.remote_commit_id, created_at=commit.created_at.isoformat())
                except Exception:
                    logger.warning("Failed to delete remote commit %s", commit.id, exc_info=True)
            session.delete(commit)
        session.commit()


def _execute_run(*, run_id: str, queue_item_id: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        config = get_or_create_backup_sync_config(session)
        _validate_config(config)
        queue_item = repo.get_backup_queue_item(session, queue_item_id)
        if queue_item is None:
            raise ResourceNotFound("Backup queue item not found")
        credentials = load_backup_credentials(config.credential_ref)

    prepared = prepare_run_artifacts(credentials, encrypt_runtime_data=bool(config.encrypt_runtime_data))
    uploaded_chunk_digests: list[str] = []
    try:
        transport = build_transport(config, credentials)
        transport.begin_session()
        commit_id = str(uuid.uuid4())
        manifest = build_manifest(
            commit_id=commit_id,
            site_slug=config.site_slug,
            transport=config.transport_mode,
            trigger_kind=queue_item.trigger_kind,
            files=prepared.files,
        )
        stats = {"chunks_total": 0, "chunks_uploaded": 0, "bytes_total": 0}

        # Batch check which chunks already exist on remote
        all_chunks: list[tuple[PreparedChunk, PreparedFile]] = []
        for prepared_file in prepared.files:
            for chunk in prepared_file.chunks:
                all_chunks.append((chunk, prepared_file))
                stats["chunks_total"] += 1
                stats["bytes_total"] += chunk.size

        all_digests = [chunk.digest for chunk, _ in all_chunks]
        existing = transport.has_chunks(all_digests) if hasattr(transport, "has_chunks") else {}
        if not existing and all_digests:
            existing = {d: transport.has_chunk(d) for d in all_digests}

        # Batch upload missing chunks
        to_upload: list[tuple[str, Path]] = []
        for chunk, _ in all_chunks:
            uploaded_chunk_digests.append(chunk.digest)
            if not existing.get(chunk.digest, False):
                to_upload.append((chunk.digest, chunk.temp_path))
                stats["chunks_uploaded"] += 1

        if hasattr(transport, "upload_chunks"):
            transport.upload_chunks(to_upload)
        else:
            for digest, chunk_path in to_upload:
                transport.upload_chunk(digest, chunk_path)

        manifest_bytes = _canonical_json(manifest)
        manifest_digest = _sha256_bytes(manifest_bytes)
        transport.upload_manifest(manifest_digest, manifest_bytes)
        remote_commit = transport.commit(commit_id=commit_id, manifest_digest=manifest_digest, manifest=manifest)

        with session_factory() as session:
            commit = repo.create_backup_commit(
                session,
                id=commit_id,
                transport=config.transport_mode,
                trigger_kind=queue_item.trigger_kind,
                site_slug=config.site_slug,
                remote_commit_id=remote_commit["remote_commit_id"],
                manifest_digest=manifest_digest,
                backup_path=remote_commit.get("backup_path"),
                datasets=manifest["datasets"],
                stats_json=stats,
                snapshot_started_at=datetime.fromisoformat(manifest["created_at"]),
                snapshot_finished_at=_utcnow(),
            )
            run = repo.get_sync_run(session, run_id)
            if run is not None:
                run.commit_id = commit.id
            queue = repo.get_backup_queue_item(session, queue_item_id)
            if queue is not None:
                queue.verified_chunks = uploaded_chunk_digests
            session.commit()

        _mark_run_completed(run_id=run_id, queue_item_id=queue_item_id, commit_id=commit_id, stats_json=stats)

        try:
            _enforce_retention(config, transport)
        except Exception:
            logger.warning("Retention cleanup failed (non-fatal)", exc_info=True)
    finally:
        shutil.rmtree(prepared.temp_dir, ignore_errors=True)


def prepare_run_artifacts(
    credentials: BackupCredentialBundle,
    *,
    encrypt_runtime_data: bool = False,
) -> PreparedRunArtifacts:
    settings = get_settings()
    run_id = uuid_str()
    temp_dir = settings.backup_sync_tmp_dir / run_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    files: list[PreparedFile] = []
    runtime_public_key = credentials.secrets_public_key if encrypt_runtime_data else None

    aerisun_snapshot = temp_dir / "aerisun.sqlite"
    waline_snapshot = temp_dir / "waline.sqlite"
    _snapshot_sqlite(settings.db_path, aerisun_snapshot)
    _snapshot_sqlite(settings.waline_db_path, waline_snapshot)

    aerisun_zst = temp_dir / "aerisun.db.zst"
    waline_zst = temp_dir / "waline.db.zst"
    _zstd_compress_file(aerisun_snapshot, aerisun_zst)
    _zstd_compress_file(waline_snapshot, waline_zst)
    aerisun_payload_path, aerisun_encryption = _prepare_runtime_payload(
        aerisun_zst,
        temp_dir=temp_dir,
        temp_name="aerisun.db.zst.enc",
        public_key=runtime_public_key,
        aad=b"datasets/aerisun.db.zst",
    )
    waline_payload_path, waline_encryption = _prepare_runtime_payload(
        waline_zst,
        temp_dir=temp_dir,
        temp_name="waline.db.zst.enc",
        public_key=runtime_public_key,
        aad=b"datasets/waline.db.zst",
    )
    files.append(
        _prepare_file(
            aerisun_payload_path,
            "datasets/aerisun.db.zst",
            chunk_root=temp_dir,
            dataset_kind="sqlite",
            compression="zstd",
            encryption=aerisun_encryption,
        )
    )
    files.append(
        _prepare_file(
            waline_payload_path,
            "datasets/waline.db.zst",
            chunk_root=temp_dir,
            dataset_kind="sqlite",
            compression="zstd",
            encryption=waline_encryption,
        )
    )

    workflow_snapshot = temp_dir / "workflow.sqlite"
    _snapshot_sqlite(settings.workflow_db_path, workflow_snapshot)
    workflow_zst = temp_dir / "workflow.db.zst"
    _zstd_compress_file(workflow_snapshot, workflow_zst)
    workflow_payload_path, workflow_encryption = _prepare_runtime_payload(
        workflow_zst,
        temp_dir=temp_dir,
        temp_name="workflow.db.zst.enc",
        public_key=runtime_public_key,
        aad=b"datasets/workflow.db.zst",
    )
    files.append(
        _prepare_file(
            workflow_payload_path,
            "datasets/workflow.db.zst",
            chunk_root=temp_dir,
            dataset_kind="workflow",
            compression="zstd",
            encryption=workflow_encryption,
        )
    )

    secrets_tar = temp_dir / "secrets.tar"
    _tar_secrets_dir(settings.secrets_dir, secrets_tar)
    secrets_zst = temp_dir / "secrets.tar.zst"
    _zstd_compress_file(secrets_tar, secrets_zst)
    secrets_enc = temp_dir / "secrets.tar.zst.enc"
    encryption_meta = _encrypt_file_for_backup(
        secrets_zst,
        secrets_enc,
        credentials.secrets_public_key,
        aad=b"datasets/secrets.tar.zst.enc",
    )
    files.append(
        _prepare_file(
            secrets_enc,
            "datasets/secrets.tar.zst.enc",
            chunk_root=temp_dir,
            dataset_kind="secrets",
            compression=None,
            encryption=encryption_meta,
        )
    )

    automation_packs_tar = temp_dir / "automation-packs.tar"
    _tar_directory(settings.data_dir / "automation" / "packs", automation_packs_tar)
    automation_packs_zst = temp_dir / "automation-packs.tar.zst"
    _zstd_compress_file(automation_packs_tar, automation_packs_zst)
    automation_packs_payload_path, automation_packs_encryption = _prepare_runtime_payload(
        automation_packs_zst,
        temp_dir=temp_dir,
        temp_name="automation-packs.tar.zst.enc",
        public_key=runtime_public_key,
        aad=b"datasets/automation-packs.tar.zst",
    )
    files.append(
        _prepare_file(
            automation_packs_payload_path,
            "datasets/automation-packs.tar.zst",
            chunk_root=temp_dir,
            dataset_kind="automation_packs",
            compression="zstd",
            encryption=automation_packs_encryption,
        )
    )

    for media_path in sorted(settings.media_dir.rglob("*")):
        if not media_path.is_file():
            continue
        relative = media_path.relative_to(settings.media_dir).as_posix()
        media_payload_path, media_encryption = _prepare_runtime_payload(
            media_path,
            temp_dir=temp_dir,
            temp_name=f"media-{uuid.uuid4().hex}.enc",
            public_key=runtime_public_key,
            aad=f"media/{relative}".encode(),
        )
        files.append(
            _prepare_file(
                media_payload_path,
                f"media/{relative}",
                chunk_root=temp_dir,
                dataset_kind="media",
                encryption=media_encryption,
            )
        )

    return PreparedRunArtifacts(
        temp_dir=temp_dir,
        files=files,
        dataset_versions=collect_dataset_versions(),
    )


def _snapshot_sqlite(source_path: Path, dest_path: Path) -> None:
    if not source_path.exists():
        dest_path.touch()
        return
    src = sqlite3.connect(source_path)
    dst = sqlite3.connect(dest_path)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()


def _atomic_file_replace(source: Path, target: Path) -> None:
    """Copy source to a temp file next to target, then atomically rename over target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f".tmp-{uuid.uuid4().hex}")
    try:
        shutil.copy2(source, tmp)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _zstd_compress_file(source: Path, dest: Path) -> None:
    compressor = zstd.ZstdCompressor(level=6)
    with source.open("rb") as src, dest.open("wb") as dst:
        compressor.copy_stream(src, dst)


def _zstd_decompress_file(source: Path, dest: Path) -> None:
    decompressor = zstd.ZstdDecompressor()
    with source.open("rb") as src, dest.open("wb") as dst:
        decompressor.copy_stream(src, dst)


def _tar_directory(source_dir: Path, dest_tar: Path, *, exclude_prefixes: tuple[str, ...] = ()) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest_tar, "w") as archive:
        for item in sorted(source_dir.rglob("*")):
            if not item.is_file():
                continue
            relative = item.relative_to(source_dir).as_posix()
            if any(relative.startswith(prefix) for prefix in exclude_prefixes):
                continue
            archive.add(item, arcname=relative)


def _tar_secrets_dir(source_dir: Path, dest_tar: Path) -> None:
    _tar_directory(source_dir, dest_tar, exclude_prefixes=("backup-sync/",))


def _restore_tar_directory(source_tar: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source_tar, "r") as archive:
        for member in archive.getmembers():
            target_path = (target_dir / member.name).resolve()
            if not str(target_path).startswith(str(target_dir.resolve())):
                raise ValidationError("Refusing to restore tar entry outside target directory")
        archive.extractall(target_dir, filter="data")


def _restore_secrets_tar(source_tar: Path, target_dir: Path) -> None:
    _restore_tar_directory(source_tar, target_dir)


def _prepare_runtime_payload(
    source: Path,
    *,
    temp_dir: Path,
    temp_name: str,
    public_key: x25519.X25519PublicKey | None,
    aad: bytes,
) -> tuple[Path, dict[str, Any] | None]:
    if public_key is None:
        return source, None
    encrypted_path = temp_dir / temp_name
    metadata = _encrypt_file_for_backup(source, encrypted_path, public_key, aad=aad)
    return encrypted_path, metadata


def _encrypt_file_for_backup(
    source: Path,
    dest: Path,
    public_key: x25519.X25519PublicKey,
    *,
    aad: bytes,
) -> dict[str, Any]:
    plaintext = source.read_bytes()
    ephemeral_private = x25519.X25519PrivateKey.generate()
    shared = ephemeral_private.exchange(public_key)
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"aerisun-backup-secrets").derive(shared)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    envelope = {
        "version": 2,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ephemeral_public_key": base64.b64encode(ephemeral_private.public_key().public_bytes_raw()).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "aad": base64.b64encode(aad).decode("ascii"),
    }
    dest.write_bytes(_canonical_json(envelope))
    return {
        "scheme": "x25519-aesgcm",
        "recipient_fingerprint": _fingerprint_public_key(public_key.public_bytes_raw()),
    }


def _decrypt_backup_file(source: Path, dest: Path, private_key: x25519.X25519PrivateKey) -> None:
    envelope = json.loads(source.read_text(encoding="utf-8"))
    ephemeral_public = x25519.X25519PublicKey.from_public_bytes(base64.b64decode(envelope["ephemeral_public_key"]))
    shared = private_key.exchange(ephemeral_public)
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=base64.b64decode(envelope["salt"]),
        info=b"aerisun-backup-secrets",
    ).derive(shared)
    aad = base64.b64decode(envelope["aad"])
    plaintext = AESGCM(key).decrypt(
        base64.b64decode(envelope["nonce"]),
        base64.b64decode(envelope["ciphertext"]),
        aad,
    )
    dest.write_bytes(plaintext)


def _load_runtime_private_key_for_fingerprint(credential_ref: str, fingerprint: str) -> x25519.X25519PrivateKey:
    candidates = [_current_private_key_path(credential_ref), _archive_private_key_path(credential_ref, fingerprint)]
    public_candidates = [
        _current_public_key_path(credential_ref),
        _archive_public_key_path(credential_ref, fingerprint),
    ]
    for private_path, public_path in zip(candidates, public_candidates, strict=False):
        if not private_path.exists() or not public_path.exists():
            continue
        public_key = serialization.load_pem_public_key(public_path.read_bytes())
        if not isinstance(public_key, x25519.X25519PublicKey):
            continue
        if _fingerprint_public_key(public_key.public_bytes_raw()) != fingerprint:
            continue
        private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
        if isinstance(private_key, x25519.X25519PrivateKey):
            return private_key
    raise ValidationError(f"Backup recovery key not found for fingerprint: {fingerprint}")


def _prepare_file(
    path: Path,
    relative_path: str,
    *,
    chunk_root: Path,
    dataset_kind: str,
    compression: str | None = None,
    encryption: dict[str, Any] | None = None,
) -> PreparedFile:
    chunks_dir = chunk_root / f".chunks-{path.stem}-{uuid.uuid4().hex}"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[PreparedChunk] = []
    with path.open("rb") as fh:
        index = 0
        while True:
            payload = fh.read(CHUNK_SIZE_BYTES)
            if not payload:
                break
            digest = _sha256_bytes(payload)
            chunk_path = chunks_dir / f"{index:06d}-{digest}.part"
            chunk_path.write_bytes(payload)
            chunks.append(PreparedChunk(digest=digest, size=len(payload), temp_path=chunk_path))
            index += 1
    return PreparedFile(
        relative_path=relative_path,
        temp_path=path,
        size=path.stat().st_size if path.exists() else 0,
        digest=_sha256_file(path) if path.exists() else _sha256_bytes(b""),
        chunks=chunks,
        dataset_kind=dataset_kind,
        compression=compression,
        encryption=encryption,
    )


def build_manifest(
    *,
    commit_id: str,
    site_slug: str,
    transport: str,
    trigger_kind: str,
    files: list[PreparedFile],
) -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    media_files: list[dict[str, Any]] = []
    for prepared_file in files:
        file_payload = {
            "path": prepared_file.relative_path,
            "digest": prepared_file.digest,
            "size": prepared_file.size,
            "chunks": [{"digest": chunk.digest, "size": chunk.size} for chunk in prepared_file.chunks],
            "compression": prepared_file.compression,
            "encryption": prepared_file.encryption,
        }
        if prepared_file.dataset_kind == "media":
            media_files.append(file_payload)
            continue
        key = {
            "datasets/aerisun.db.zst": "aerisun_db",
            "datasets/waline.db.zst": "waline_db",
            "datasets/workflow.db.zst": "workflow_db",
            "datasets/secrets.tar.zst.enc": "secrets",
            "datasets/automation-packs.tar.zst": "automation_packs",
        }[prepared_file.relative_path]
        file_payload["target_path"] = prepared_file.relative_path.split("/", 1)[1]
        datasets[key] = file_payload
    datasets["media"] = {"files": media_files}
    return {
        "version": MANIFEST_VERSION,
        "commit_id": commit_id,
        "site_slug": site_slug,
        "transport": transport,
        "trigger_kind": trigger_kind,
        "created_at": _utcnow().isoformat(),
        "chunk_algorithm": CHUNK_DIGEST_ALGORITHM,
        "datasets": datasets,
    }


def build_transport(config, _credentials: BackupCredentialBundle) -> BackupTransport:
    return SftpTransport(
        host=config.remote_host,
        port=config.remote_port or 22,
        username=config.remote_username,
        remote_root=config.remote_path,
        site_slug=config.site_slug,
    )


class SftpTransport:
    def __init__(self, *, host: str, port: int, username: str, remote_root: str, site_slug: str) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._remote_root = remote_root.rstrip("/")
        self._site_slug = site_slug

    def begin_session(self) -> dict[str, Any]:
        self._mkdirs(self._site_root(), self._catalog_root(), self._commits_root(), self._datasets_root())
        return {"session_id": uuid_str(), "site_slug": self._site_slug}

    def probe_write_access(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write("backup-probe\n")
            tmp_path = Path(tmp.name)
        probe_remote = f"{self._catalog_root()}/probes/{uuid_str()}.txt"
        try:
            self._mkdirs(str(PurePosixPath(probe_remote).parent))
            self._run_batch([f"put {tmp_path} {probe_remote}", f"rm {probe_remote}"])
        finally:
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _sanitize_sftp_path(path: str) -> str:
        if _SFTP_UNSAFE_RE.search(path):
            raise ValidationError(f"SFTP path contains unsafe characters: {path!r}")
        return path

    def _run_batch(self, commands: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        sanitized = [self._sanitize_sftp_path(cmd) for cmd in commands]
        payload = "\n".join(sanitized) + "\n"
        proc = subprocess.run(
            ["sftp", "-P", str(self._port), "-b", "-", f"{self._username}@{self._host}"],
            input=payload,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and proc.returncode != 0:
            raise ValidationError(proc.stderr.strip() or "SFTP command failed")
        return proc

    def _mkdirs(self, *paths: str) -> None:
        commands: list[str] = []
        seen: set[str] = set()
        for remote_path in paths:
            current = PurePosixPath("/")
            for part in PurePosixPath(remote_path).parts:
                if part == "/":
                    current = PurePosixPath("/")
                    continue
                current = current / part
                posix = current.as_posix()
                if posix not in seen:
                    seen.add(posix)
                    commands.append(f"mkdir {posix}")
        self._run_batch(commands, check=False)

    def _site_root(self) -> str:
        return self._remote_root

    def _catalog_root(self) -> str:
        return f"{self._site_root()}/catalog"

    def _commits_root(self) -> str:
        return f"{self._site_root()}/commits"

    def _datasets_root(self) -> str:
        return f"{self._site_root()}/datasets"

    def _chunk_path(self, digest: str) -> str:
        return f"{self._catalog_root()}/chunks/{digest[:2]}/{digest[2:4]}/{digest}"

    def _manifest_path(self, digest: str) -> str:
        return f"{self._catalog_root()}/manifests/{digest}.json"

    def _commit_index_path(self, commit_id: str) -> str:
        return f"{self._catalog_root()}/commit-index/{commit_id}.json"

    def _human_commit_dir(self, commit_id: str, created_at: str) -> str:
        dt = datetime.fromisoformat(created_at)
        return f"{self._commits_root()}/{dt:%Y/%m/%d}/{dt:%Y%m%dT%H%M%SZ}-{commit_id}"

    def has_chunk(self, digest: str) -> bool:
        proc = self._run_batch([f"ls {self._chunk_path(digest)}"], check=False)
        return proc.returncode == 0

    def has_chunks(self, digests: list[str]) -> dict[str, bool]:
        """Check existence of multiple chunks in a single SFTP session."""
        if not digests:
            return {}
        commands = [f"ls {self._chunk_path(d)}" for d in digests]
        proc = self._run_batch(commands, check=False)
        stdout_lines = (proc.stdout or "").splitlines()
        stderr_text = proc.stderr or ""
        result: dict[str, bool] = {}
        for d in digests:
            chunk_path = self._chunk_path(d)
            if "not found" in stderr_text and chunk_path in stderr_text:
                result[d] = False
            elif any(d in line for line in stdout_lines):
                result[d] = True
            else:
                result[d] = "Cannot stat" not in stderr_text or chunk_path not in stderr_text
        return result

    def upload_chunk(self, digest: str, chunk_path: Path) -> None:
        remote = self._chunk_path(digest)
        self._mkdirs(str(PurePosixPath(remote).parent))
        self._run_batch([f"put {chunk_path} {remote}"])

    def upload_chunks(self, chunks: list[tuple[str, Path]]) -> None:
        """Upload multiple chunks in a single SFTP session."""
        if not chunks:
            return
        parent_dirs: set[str] = set()
        for digest, _ in chunks:
            parent_dirs.add(str(PurePosixPath(self._chunk_path(digest)).parent))
        self._mkdirs(*parent_dirs)
        commands = [f"put {chunk_path} {self._chunk_path(digest)}" for digest, chunk_path in chunks]
        self._run_batch(commands)

    def upload_manifest(self, digest: str, payload: bytes) -> None:
        with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        try:
            remote = self._manifest_path(digest)
            self._mkdirs(str(PurePosixPath(remote).parent))
            self._run_batch([f"put {tmp_path} {remote}"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def commit(self, *, commit_id: str, manifest_digest: str, manifest: dict[str, Any]) -> dict[str, Any]:
        commit_dir = self._human_commit_dir(commit_id, manifest["created_at"])
        backup_path = f"{commit_dir}/manifest.json"
        index_remote = self._commit_index_path(commit_id)
        index_payload = {
            "commit_id": commit_id,
            "site_slug": self._site_slug,
            "remote_commit_id": commit_id,
            "manifest_digest": manifest_digest,
            "backup_path": backup_path,
            "created_at": manifest["created_at"],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write(json.dumps(index_payload, ensure_ascii=False))
            tmp_path = Path(tmp.name)
        try:
            self._mkdirs(commit_dir, str(PurePosixPath(index_remote).parent))
            self._run_batch(
                [
                    f"put {tmp_path} {backup_path}",
                    f"put {tmp_path} {index_remote}",
                ]
            )
        finally:
            tmp_path.unlink(missing_ok=True)
        return {"remote_commit_id": commit_id, "backup_path": backup_path}

    def delete_commit(self, commit_id: str, *, created_at: str) -> None:
        """Remove a commit's index entry and human-readable directory from remote."""
        index_path = self._commit_index_path(commit_id)
        commit_dir = self._human_commit_dir(commit_id, created_at)
        self._run_batch(
            [f"rm {index_path}", f"rm {commit_dir}/manifest.json"],
            check=False,
        )

    def list_commits(self) -> list[dict[str, Any]]:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_dir = Path(temp_dir)
            remote_dir = f"{self._catalog_root()}/commit-index"
            self._run_batch([f"get -r {remote_dir} {local_dir}"], check=False)
            index_dir = local_dir / "commit-index"
            if not index_dir.exists():
                return []
            items = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(index_dir.glob("*.json"))]
            return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)

    def fetch_commit(self, commit_id: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / f"{commit_id}.json"
            self._run_batch([f"get {self._commit_index_path(commit_id)} {local_path}"])
            return json.loads(local_path.read_text(encoding="utf-8"))

    def fetch_manifest(self, digest: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / f"{digest}.json"
            self._run_batch([f"get {self._manifest_path(digest)} {local_path}"])
            return json.loads(local_path.read_text(encoding="utf-8"))

    def read_chunk(self, digest: str) -> bytes:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / digest
            self._run_batch([f"get {self._chunk_path(digest)} {local_path}"])
            return local_path.read_bytes()


def restore_backup_commit(session: Session, commit_id: str) -> BackupCommitRead:
    commit = repo.get_backup_commit(session, commit_id)
    if commit is None:
        raise ResourceNotFound("Backup commit not found")
    config = get_or_create_backup_sync_config(session)
    credentials = load_backup_credentials(config.credential_ref)
    transport = build_transport(config, credentials)
    commit_payload = transport.fetch_commit(commit.remote_commit_id)
    manifest = transport.fetch_manifest(commit_payload["manifest_digest"])
    _restore_from_manifest(manifest, transport, credentials)
    commit.restored_at = _utcnow()
    session.commit()
    session.refresh(commit)
    return _commit_read(commit)


def restore_backup_snapshot(session: Session, snapshot_id: str) -> BackupSnapshotRead:
    commit = repo.get_backup_commit(session, snapshot_id)
    if commit is None:
        raise ResourceNotFound("Backup snapshot not found")
    restore_backup_commit(session, snapshot_id)
    session.refresh(commit)
    return _to_snapshot(commit)


def _restore_from_manifest(
    manifest: dict[str, Any],
    transport: BackupTransport,
    credentials: BackupCredentialBundle,
) -> None:
    settings = get_settings()
    temp_dir = settings.backup_sync_tmp_dir / f"restore-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with _restore_lock:
        _restore_in_progress.set()
    try:
        datasets = manifest["datasets"]

        aerisun_zst = _materialize_manifest_payload(temp_dir, datasets["aerisun_db"], transport, credentials)
        waline_zst = _materialize_manifest_payload(temp_dir, datasets["waline_db"], transport, credentials)
        workflow_entry = datasets.get("workflow_db")
        workflow_zst = (
            _materialize_manifest_payload(temp_dir, workflow_entry, transport, credentials) if workflow_entry else None
        )
        secrets_enc = _materialize_manifest_file(temp_dir, datasets["secrets"], transport)
        automation_packs_entry = datasets.get("automation_packs")
        automation_packs_zst = (
            _materialize_manifest_payload(temp_dir, automation_packs_entry, transport, credentials)
            if automation_packs_entry
            else None
        )

        aerisun_restore = temp_dir / "aerisun.restore.sqlite"
        waline_restore = temp_dir / "waline.restore.sqlite"
        workflow_restore = temp_dir / "workflow.restore.sqlite"
        secrets_zst = temp_dir / "secrets.tar.zst"
        secrets_tar = temp_dir / "secrets.tar"
        automation_packs_tar = temp_dir / "automation-packs.tar"

        _zstd_decompress_file(aerisun_zst, aerisun_restore)
        _zstd_decompress_file(waline_zst, waline_restore)
        if workflow_zst is not None:
            _zstd_decompress_file(workflow_zst, workflow_restore)
        _decrypt_backup_file(secrets_enc, secrets_zst, credentials.secrets_private_key)
        _zstd_decompress_file(secrets_zst, secrets_tar)
        if automation_packs_zst is not None:
            _zstd_decompress_file(automation_packs_zst, automation_packs_tar)

        # --- Atomic swap: databases via temp file + os.replace ---
        _atomic_file_replace(aerisun_restore, settings.db_path)
        _atomic_file_replace(waline_restore, settings.waline_db_path)
        if workflow_zst is not None:
            _atomic_file_replace(workflow_restore, settings.workflow_db_path)

        # --- Media: stage into sibling dir, then swap ---
        staging_media = settings.media_dir.parent / f".media-staging-{uuid.uuid4().hex}"
        staging_media.mkdir(parents=True, exist_ok=True)
        for file_entry in datasets["media"]["files"]:
            target_path = (staging_media / file_entry["path"].removeprefix("media/")).resolve()
            if not str(target_path).startswith(str(staging_media.resolve())):
                raise ValidationError("Refusing to restore media file outside media directory")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            source_path = _materialize_manifest_payload(temp_dir, file_entry, transport, credentials)
            shutil.copy2(source_path, target_path)
        old_media = settings.media_dir.parent / f".media-old-{uuid.uuid4().hex}"
        if settings.media_dir.exists():
            os.rename(settings.media_dir, old_media)
        os.rename(staging_media, settings.media_dir)
        if old_media.exists():
            shutil.rmtree(old_media, ignore_errors=True)

        # --- Secrets: stage, then swap (preserve backup-sync dir) ---
        staging_secrets = settings.secrets_dir.parent / f".secrets-staging-{uuid.uuid4().hex}"
        staging_secrets.mkdir(parents=True, exist_ok=True)
        _restore_secrets_tar(secrets_tar, staging_secrets)
        if settings.secrets_dir.exists():
            backup_sync_dir = settings.secrets_dir / "backup-sync"
            if backup_sync_dir.exists():
                shutil.copytree(backup_sync_dir, staging_secrets / "backup-sync", dirs_exist_ok=True)
        old_secrets = settings.secrets_dir.parent / f".secrets-old-{uuid.uuid4().hex}"
        if settings.secrets_dir.exists():
            os.rename(settings.secrets_dir, old_secrets)
        os.rename(staging_secrets, settings.secrets_dir)
        if old_secrets.exists():
            shutil.rmtree(old_secrets, ignore_errors=True)

        # --- Automation packs: stage, then swap ---
        if automation_packs_zst is not None:
            automation_packs_root = settings.data_dir / "automation" / "packs"
            staging_packs = automation_packs_root.parent / f".packs-staging-{uuid.uuid4().hex}"
            staging_packs.mkdir(parents=True, exist_ok=True)
            _restore_tar_directory(automation_packs_tar, staging_packs)
            old_packs = automation_packs_root.parent / f".packs-old-{uuid.uuid4().hex}"
            if automation_packs_root.exists():
                os.rename(automation_packs_root, old_packs)
            os.rename(staging_packs, automation_packs_root)
            if old_packs.exists():
                shutil.rmtree(old_packs, ignore_errors=True)
    finally:
        _restore_in_progress.clear()
        shutil.rmtree(temp_dir, ignore_errors=True)


def _materialize_manifest_file(temp_dir: Path, entry: dict[str, Any], transport: BackupTransport) -> Path:
    local_path = temp_dir / Path(entry["path"]).name
    _write_chunks_to_path(entry["chunks"], local_path, transport)
    if _sha256_file(local_path) != entry["digest"]:
        raise ValidationError(f"Checksum mismatch while restoring {entry['path']}")
    return local_path


def _materialize_manifest_payload(
    temp_dir: Path,
    entry: dict[str, Any],
    transport: BackupTransport,
    credentials: BackupCredentialBundle,
) -> Path:
    payload_path = _materialize_manifest_file(temp_dir, entry, transport)
    encryption = entry.get("encryption") or {}
    if not encryption:
        return payload_path
    if encryption.get("scheme") != "x25519-aesgcm":
        raise ValidationError(f"Unsupported backup encryption scheme: {encryption.get('scheme')}")
    recipient_fingerprint = str(encryption.get("recipient_fingerprint") or "").strip()
    if not recipient_fingerprint:
        raise ValidationError("Encrypted backup payload is missing recipient_fingerprint")
    plaintext_path = payload_path.with_suffix(payload_path.suffix + ".plain")
    private_key = _load_runtime_private_key_for_fingerprint(credentials.credential_ref, recipient_fingerprint)
    _decrypt_backup_file(payload_path, plaintext_path, private_key)
    return plaintext_path


def _write_chunks_to_path(chunks: list[dict[str, Any]], destination: Path, transport: BackupTransport) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as fh:
        for chunk in chunks:
            payload = transport.read_chunk(chunk["digest"])
            if _sha256_bytes(payload) != chunk["digest"]:
                raise ValidationError("Downloaded backup chunk digest mismatch")
            fh.write(payload)
