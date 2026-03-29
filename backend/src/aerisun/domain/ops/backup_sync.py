from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

import httpx
import zstandard as zstd
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.orm import Session

from aerisun.core.base import uuid_str
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.ops import repository as repo
from aerisun.domain.ops.schemas import (
    BackupCommitRead,
    BackupQueueItemRead,
    BackupRunRead,
    BackupSnapshotRead,
    BackupSyncConfig,
    BackupSyncConfigUpdate,
    BackupTransportConfig,
)

CHUNK_SIZE_BYTES = 8 * 1024 * 1024
BACKUP_JOB_NAME = "backup_sync"
CHUNK_DIGEST_ALGORITHM = "sha256"
MANIFEST_VERSION = 1


@dataclass(slots=True)
class BackupCredentialBundle:
    credential_ref: str
    signing_private_key: ed25519.Ed25519PrivateKey
    signing_public_key: ed25519.Ed25519PublicKey
    secrets_private_key: x25519.X25519PrivateKey
    secrets_public_key: x25519.X25519PublicKey
    signing_fingerprint: str
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
    settings = get_settings()
    key_dir = settings.secrets_dir / "backup-sync" / credential_ref
    signing_private = serialization.load_pem_private_key(_load_pem_bytes(key_dir / "client_ed25519.pem"), password=None)
    signing_public = serialization.load_pem_public_key(_load_pem_bytes(key_dir / "client_ed25519.pub.pem"))
    if not isinstance(signing_private, ed25519.Ed25519PrivateKey):
        raise ValidationError("Backup signing private key must be an Ed25519 key")
    if not isinstance(signing_public, ed25519.Ed25519PublicKey):
        raise ValidationError("Backup signing public key must be an Ed25519 key")

    secrets_private = serialization.load_pem_private_key(_load_pem_bytes(key_dir / "secrets_x25519.pem"), password=None)
    secrets_public = serialization.load_pem_public_key(_load_pem_bytes(key_dir / "secrets_x25519.pub.pem"))
    if not isinstance(secrets_private, x25519.X25519PrivateKey):
        raise ValidationError("Backup secrets private key must be an X25519 key")
    if not isinstance(secrets_public, x25519.X25519PublicKey):
        raise ValidationError("Backup secrets public key must be an X25519 key")

    return BackupCredentialBundle(
        credential_ref=credential_ref,
        signing_private_key=signing_private,
        signing_public_key=signing_public,
        secrets_private_key=secrets_private,
        secrets_public_key=secrets_public,
        signing_fingerprint=_fingerprint_public_key(signing_public.public_bytes_raw()),
        secrets_fingerprint=_fingerprint_public_key(secrets_public.public_bytes_raw()),
    )


def _build_transport_config(config) -> BackupTransportConfig:
    return BackupTransportConfig(
        mode=config.transport_mode,
        receiver_base_url=config.receiver_base_url,
        remote_host=config.remote_host,
        remote_port=config.remote_port,
        remote_path=config.remote_path,
        remote_username=config.remote_username,
    )


def _config_read(config) -> BackupSyncConfig:
    return BackupSyncConfig(
        id=config.id,
        enabled=config.enabled,
        paused=config.paused,
        interval_minutes=config.interval_minutes,
        transport_mode=config.transport_mode,
        site_slug=config.site_slug,
        credential_ref=config.credential_ref,
        age_public_key_fingerprint=config.age_public_key_fingerprint,
        max_retries=config.max_retries,
        retry_backoff_seconds=config.retry_backoff_seconds,
        last_scheduled_at=config.last_scheduled_at,
        last_synced_at=config.last_synced_at,
        last_error=config.last_error,
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


def get_or_create_backup_sync_config(session: Session):
    settings = get_settings()
    config = repo.get_backup_target_config(session)
    if config is None:
        config = repo.create_backup_target_config(
            session,
            enabled=False,
            paused=False,
            interval_minutes=settings.backup_sync_default_interval_minutes,
            transport_mode="receiver",
            site_slug=settings.backup_sync_default_site_slug,
            remote_port=settings.backup_ssh_port,
            max_retries=3,
            retry_backoff_seconds=300,
        )
        session.commit()
        session.refresh(config)
    return config


def get_backup_sync_config(session: Session) -> BackupSyncConfig:
    return _config_read(get_or_create_backup_sync_config(session))


def update_backup_sync_config(session: Session, payload: BackupSyncConfigUpdate) -> BackupSyncConfig:
    config = get_or_create_backup_sync_config(session)
    config.enabled = payload.enabled
    config.paused = payload.paused
    config.interval_minutes = max(payload.interval_minutes, 1)
    config.transport_mode = payload.transport_mode
    config.site_slug = payload.site_slug.strip() or get_settings().backup_sync_default_site_slug
    config.receiver_base_url = payload.receiver_base_url
    config.remote_host = payload.remote_host
    config.remote_port = payload.remote_port
    config.remote_path = payload.remote_path
    config.remote_username = payload.remote_username
    config.credential_ref = payload.credential_ref
    config.age_public_key_fingerprint = payload.age_public_key_fingerprint
    config.max_retries = max(payload.max_retries, 0)
    config.retry_backoff_seconds = max(payload.retry_backoff_seconds, 30)
    _validate_config(config)
    session.commit()
    session.refresh(config)
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


def list_backup_snapshots_compat(session: Session) -> list[BackupSnapshotRead]:
    return [_to_snapshot(item) for item in repo.list_backup_commits(session)]


def _validate_config(config) -> None:
    if config.transport_mode not in {"receiver", "sftp"}:
        raise ValidationError("Backup transport mode must be receiver or sftp")
    if not config.credential_ref:
        raise ValidationError("Backup credential_ref is required")
    if config.transport_mode == "receiver" and not config.receiver_base_url:
        raise ValidationError("Receiver transport requires receiver_base_url")
    if config.transport_mode == "sftp" and (
        not config.remote_host or not config.remote_path or not config.remote_username
    ):
        raise ValidationError("SFTP transport requires remote_host, remote_path, and remote_username")


def collect_dataset_versions() -> dict[str, Any]:
    settings = get_settings()

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
    return {
        "aerisun_db": _path_info(settings.db_path),
        "waline_db": _path_info(settings.waline_db_path),
        "media": {
            "file_count": len(media_files),
            "paths_digest": _sha256_bytes("\n".join(media_files).encode("utf-8")),
        },
        "secrets": {
            "file_count": len(secret_files),
            "paths_digest": _sha256_bytes("\n".join(secret_files).encode("utf-8")),
        },
    }


def ensure_backup_queue_item(session: Session, *, trigger_kind: str, force: bool = False):
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
    dispatch_backup_sync()
    session.refresh(run)
    return _run_read(run)


def dispatch_backup_sync() -> BackupRunRead | None:
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

    try:
        _execute_run(run_id=run_id, queue_item_id=queue_item_id)
    except Exception as exc:
        _mark_run_failed(run_id=run_id, queue_item_id=queue_item_id, error=str(exc))
    with session_factory() as session:
        run = repo.get_sync_run(session, run_id)
        return _run_read(run) if run is not None else None


def _mark_run_failed(*, run_id: str, queue_item_id: str, error: str) -> None:
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


def _mark_run_completed(
    *,
    run_id: str,
    queue_item_id: str,
    commit_id: str,
    stats_json: dict[str, Any],
) -> None:
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


def _execute_run(*, run_id: str, queue_item_id: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        config = get_or_create_backup_sync_config(session)
        _validate_config(config)
        queue_item = repo.get_backup_queue_item(session, queue_item_id)
        if queue_item is None:
            raise ResourceNotFound("Backup queue item not found")
        credentials = load_backup_credentials(config.credential_ref)

    prepared = prepare_run_artifacts(credentials)
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
        for prepared_file in prepared.files:
            for chunk in prepared_file.chunks:
                stats["chunks_total"] += 1
                stats["bytes_total"] += chunk.size
                if transport.has_chunk(chunk.digest):
                    uploaded_chunk_digests.append(chunk.digest)
                    continue
                transport.upload_chunk(chunk.digest, chunk.temp_path)
                uploaded_chunk_digests.append(chunk.digest)
                stats["chunks_uploaded"] += 1

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
    finally:
        shutil.rmtree(prepared.temp_dir, ignore_errors=True)


def prepare_run_artifacts(credentials: BackupCredentialBundle) -> PreparedRunArtifacts:
    settings = get_settings()
    run_id = uuid_str()
    temp_dir = settings.backup_sync_tmp_dir / run_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    files: list[PreparedFile] = []

    aerisun_snapshot = temp_dir / "aerisun.sqlite"
    waline_snapshot = temp_dir / "waline.sqlite"
    _snapshot_sqlite(settings.db_path, aerisun_snapshot)
    _snapshot_sqlite(settings.waline_db_path, waline_snapshot)

    aerisun_zst = temp_dir / "aerisun.db.zst"
    waline_zst = temp_dir / "waline.db.zst"
    _zstd_compress_file(aerisun_snapshot, aerisun_zst)
    _zstd_compress_file(waline_snapshot, waline_zst)
    files.append(
        _prepare_file(
            aerisun_zst,
            "datasets/aerisun.db.zst",
            chunk_root=temp_dir,
            dataset_kind="sqlite",
            compression="zstd",
        )
    )
    files.append(
        _prepare_file(
            waline_zst,
            "datasets/waline.db.zst",
            chunk_root=temp_dir,
            dataset_kind="sqlite",
            compression="zstd",
        )
    )

    secrets_tar = temp_dir / "secrets.tar"
    _tar_secrets_dir(settings.secrets_dir, secrets_tar)
    secrets_zst = temp_dir / "secrets.tar.zst"
    _zstd_compress_file(secrets_tar, secrets_zst)
    secrets_enc = temp_dir / "secrets.tar.zst.enc"
    encryption_meta = _encrypt_file_for_backup(secrets_zst, secrets_enc, credentials.secrets_public_key)
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

    for media_path in sorted(settings.media_dir.rglob("*")):
        if not media_path.is_file():
            continue
        relative = media_path.relative_to(settings.media_dir).as_posix()
        files.append(_prepare_file(media_path, f"media/{relative}", chunk_root=temp_dir, dataset_kind="media"))

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


def _zstd_compress_file(source: Path, dest: Path) -> None:
    compressor = zstd.ZstdCompressor(level=6)
    with source.open("rb") as src, dest.open("wb") as dst:
        compressor.copy_stream(src, dst)


def _zstd_decompress_file(source: Path, dest: Path) -> None:
    decompressor = zstd.ZstdDecompressor()
    with source.open("rb") as src, dest.open("wb") as dst:
        decompressor.copy_stream(src, dst)


def _tar_secrets_dir(source_dir: Path, dest_tar: Path) -> None:
    with tarfile.open(dest_tar, "w") as archive:
        for item in sorted(source_dir.rglob("*")):
            if not item.is_file():
                continue
            relative = item.relative_to(source_dir).as_posix()
            if relative.startswith("backup-sync/"):
                continue
            archive.add(item, arcname=relative)


def _restore_secrets_tar(source_tar: Path, target_dir: Path) -> None:
    with tarfile.open(source_tar, "r") as archive:
        for member in archive.getmembers():
            target_path = (target_dir / member.name).resolve()
            if not str(target_path).startswith(str(target_dir.resolve())):
                raise ValidationError("Refusing to restore secrets file outside target directory")
        archive.extractall(target_dir, filter="data")


def _encrypt_file_for_backup(source: Path, dest: Path, public_key: x25519.X25519PublicKey) -> dict[str, Any]:
    plaintext = source.read_bytes()
    ephemeral_private = x25519.X25519PrivateKey.generate()
    shared = ephemeral_private.exchange(public_key)
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"aerisun-backup-secrets").derive(shared)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    envelope = {
        "version": 1,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ephemeral_public_key": base64.b64encode(ephemeral_private.public_key().public_bytes_raw()).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
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
    plaintext = AESGCM(key).decrypt(
        base64.b64decode(envelope["nonce"]),
        base64.b64decode(envelope["ciphertext"]),
        None,
    )
    dest.write_bytes(plaintext)


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
            "datasets/secrets.tar.zst.enc": "secrets",
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


def build_transport(config, credentials: BackupCredentialBundle) -> BackupTransport:
    if config.transport_mode == "receiver":
        return ReceiverTransport(
            base_url=config.receiver_base_url.rstrip("/"),
            site_slug=config.site_slug,
            credentials=credentials,
        )
    return SftpTransport(
        host=config.remote_host,
        port=config.remote_port or 22,
        username=config.remote_username,
        remote_root=config.remote_path,
        site_slug=config.site_slug,
    )


class ReceiverTransport:
    def __init__(self, *, base_url: str, site_slug: str, credentials: BackupCredentialBundle) -> None:
        self._base_url = base_url
        self._site_slug = site_slug
        self._credentials = credentials
        self._session_id: str | None = None
        self._client = httpx.Client(timeout=30.0)

    def _signed_headers(self, method: str, path: str, body: bytes = b"") -> dict[str, str]:
        timestamp = str(int(_utcnow().timestamp()))
        body_digest = _sha256_bytes(body)
        message = "\n".join([method.upper(), path, self._site_slug, timestamp, body_digest]).encode("utf-8")
        signature = self._credentials.signing_private_key.sign(message)
        return {
            "X-Backup-Site": self._site_slug,
            "X-Backup-Key": self._credentials.signing_fingerprint,
            "X-Backup-Timestamp": timestamp,
            "X-Backup-Signature": base64.b64encode(signature).decode("ascii"),
        }

    def begin_session(self) -> dict[str, Any]:
        payload = {"site_slug": self._site_slug}
        body = _canonical_json(payload)
        path = "/v1/sessions"
        response = self._client.post(
            f"{self._base_url}{path}", content=body, headers=self._signed_headers("POST", path, body)
        )
        response.raise_for_status()
        data = response.json()
        self._session_id = data["session_id"]
        return data

    def has_chunk(self, digest: str) -> bool:
        path = f"/v1/chunks/{digest}"
        response = self._client.get(f"{self._base_url}{path}", headers=self._signed_headers("GET", path))
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def upload_chunk(self, digest: str, chunk_path: Path) -> None:
        body = chunk_path.read_bytes()
        path = f"/v1/chunks/{digest}"
        headers = self._signed_headers("PUT", path, body)
        if self._session_id:
            headers["X-Backup-Session"] = self._session_id
        response = self._client.put(f"{self._base_url}{path}", content=body, headers=headers)
        response.raise_for_status()

    def upload_manifest(self, digest: str, payload: bytes) -> None:
        path = f"/v1/manifests/{digest}"
        headers = self._signed_headers("PUT", path, payload)
        if self._session_id:
            headers["X-Backup-Session"] = self._session_id
        response = self._client.put(f"{self._base_url}{path}", content=payload, headers=headers)
        response.raise_for_status()

    def commit(self, *, commit_id: str, manifest_digest: str, manifest: dict[str, Any]) -> dict[str, Any]:
        payload = {"commit_id": commit_id, "manifest_digest": manifest_digest, "manifest": manifest}
        body = _canonical_json(payload)
        path = "/v1/commits"
        headers = self._signed_headers("POST", path, body)
        if self._session_id:
            headers["X-Backup-Session"] = self._session_id
        response = self._client.post(f"{self._base_url}{path}", content=body, headers=headers)
        response.raise_for_status()
        return response.json()

    def list_commits(self) -> list[dict[str, Any]]:
        path = "/v1/commits"
        response = self._client.get(f"{self._base_url}{path}", headers=self._signed_headers("GET", path))
        response.raise_for_status()
        return response.json()["items"]

    def fetch_commit(self, commit_id: str) -> dict[str, Any]:
        path = f"/v1/commits/{commit_id}"
        response = self._client.get(f"{self._base_url}{path}", headers=self._signed_headers("GET", path))
        response.raise_for_status()
        return response.json()

    def fetch_manifest(self, digest: str) -> dict[str, Any]:
        path = f"/v1/manifests/{digest}"
        response = self._client.get(f"{self._base_url}{path}", headers=self._signed_headers("GET", path))
        response.raise_for_status()
        return response.json()

    def read_chunk(self, digest: str) -> bytes:
        path = f"/v1/chunks/{digest}/download"
        response = self._client.get(f"{self._base_url}{path}", headers=self._signed_headers("GET", path))
        response.raise_for_status()
        return response.content


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

    def _run_batch(self, commands: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        payload = "\n".join(commands) + "\n"
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
        for remote_path in paths:
            current = PurePosixPath("/")
            for part in PurePosixPath(remote_path).parts:
                if part == "/":
                    current = PurePosixPath("/")
                    continue
                current = current / part
                commands.append(f"mkdir {current.as_posix()}")
        self._run_batch(commands, check=False)

    def _site_root(self) -> str:
        return f"{self._remote_root}/sites/{self._site_slug}"

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

    def upload_chunk(self, digest: str, chunk_path: Path) -> None:
        remote = self._chunk_path(digest)
        self._mkdirs(str(PurePosixPath(remote).parent))
        self._run_batch([f"put {chunk_path} {remote}"])

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


def restore_backup_snapshot_compat(session: Session, snapshot_id: str) -> BackupSnapshotRead:
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
    try:
        datasets = manifest["datasets"]

        aerisun_zst = _materialize_manifest_file(temp_dir, datasets["aerisun_db"], transport)
        waline_zst = _materialize_manifest_file(temp_dir, datasets["waline_db"], transport)
        secrets_enc = _materialize_manifest_file(temp_dir, datasets["secrets"], transport)

        aerisun_restore = temp_dir / "aerisun.restore.sqlite"
        waline_restore = temp_dir / "waline.restore.sqlite"
        secrets_zst = temp_dir / "secrets.tar.zst"
        secrets_tar = temp_dir / "secrets.tar"

        _zstd_decompress_file(aerisun_zst, aerisun_restore)
        _zstd_decompress_file(waline_zst, waline_restore)
        _decrypt_backup_file(secrets_enc, secrets_zst, credentials.secrets_private_key)
        _zstd_decompress_file(secrets_zst, secrets_tar)

        shutil.copy2(aerisun_restore, settings.db_path)
        shutil.copy2(waline_restore, settings.waline_db_path)

        if settings.media_dir.exists():
            shutil.rmtree(settings.media_dir)
        settings.media_dir.mkdir(parents=True, exist_ok=True)

        for file_entry in datasets["media"]["files"]:
            target_path = (settings.media_dir / file_entry["path"].removeprefix("media/")).resolve()
            if not str(target_path).startswith(str(settings.media_dir.resolve())):
                raise ValidationError("Refusing to restore media file outside media directory")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            _write_chunks_to_path(file_entry["chunks"], target_path, transport)

        if settings.secrets_dir.exists():
            for item in settings.secrets_dir.iterdir():
                if item.name == "backup-sync":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink(missing_ok=True)
        settings.secrets_dir.mkdir(parents=True, exist_ok=True)
        _restore_secrets_tar(secrets_tar, settings.secrets_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _materialize_manifest_file(temp_dir: Path, entry: dict[str, Any], transport: BackupTransport) -> Path:
    local_path = temp_dir / Path(entry["path"]).name
    _write_chunks_to_path(entry["chunks"], local_path, transport)
    if _sha256_file(local_path) != entry["digest"]:
        raise ValidationError(f"Checksum mismatch while restoring {entry['path']}")
    return local_path


def _write_chunks_to_path(chunks: list[dict[str, Any]], destination: Path, transport: BackupTransport) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as fh:
        for chunk in chunks:
            payload = transport.read_chunk(chunk["digest"])
            if _sha256_bytes(payload) != chunk["digest"]:
                raise ValidationError("Downloaded backup chunk digest mismatch")
            fh.write(payload)
