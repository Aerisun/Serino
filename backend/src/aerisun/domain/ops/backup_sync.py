from __future__ import annotations

import base64
import copy
import hashlib
import json
import logging
import os
import re
import secrets
import shlex
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Protocol
from urllib.parse import urlparse

import zstandard as zstd
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy.orm import Session

from aerisun.core.base import uuid_str
from aerisun.core.db import dispose_engine, get_session_factory
from aerisun.core.settings import get_settings
from aerisun.core.time import normalize_shanghai_datetime, shanghai_now
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.ops import repository as repo
from aerisun.domain.ops.schemas import (
    BackupBootstrapClaimCreate,
    BackupBootstrapClaimRead,
    BackupBootstrapClaimResultWrite,
    BackupCommitRead,
    BackupCredentialAcknowledgeWrite,
    BackupCredentialEnsureRead,
    BackupCredentialExportRead,
    BackupCredentialExportWrite,
    BackupQueueItemRead,
    BackupRemoteHistoryCommitRead,
    BackupRemoteHistoryImportPreviewRead,
    BackupRemoteHistoryImportWrite,
    BackupRemoteHistoryRestoreWrite,
    BackupRunRead,
    BackupSnapshotRead,
    BackupSyncConfig,
    BackupSyncConfigTestRead,
    BackupSyncConfigUpdate,
    BackupSystemResetRead,
    BackupTransportConfig,
)

CHUNK_SIZE_BYTES = 8 * 1024 * 1024
BACKUP_JOB_NAME = "backup_sync"
CHUNK_DIGEST_ALGORITHM = "sha256"
MANIFEST_VERSION = 1
BACKUP_BOOTSTRAP_DEFAULT_TTL_MINUTES = 10
BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME = "serino-backup"
BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH = "/srv/serino-backups"
BACKUP_BOOTSTRAP_DEFAULT_CREDENTIAL_REF = "aerisun-backup-source"
BACKUP_BOOTSTRAP_SSH_KEY_NAME = "serino_backup_ed25519"
BACKUP_REPO_IDENTITY_VERSION = 1
BACKUP_SYNC_CONFIG_TEST_TIMEOUT_SECONDS = 3
BACKUP_RETENTION_TOMBSTONE_TRIGGER = "retention-pruned"

_restore_lock = threading.Lock()
_restore_in_progress = threading.Event()
_retention_cleanup_lock = threading.Lock()

_SFTP_UNSAFE_RE = re.compile(r"[\n\r]")
_SSH_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SSH_HOST_UNSAFE_RE = re.compile(r"[\s/@]")
_REMOTE_MISSING_MARKERS = (
    "no such file",
    "not found",
    "couldn't stat remote file",
    "cannot stat",
    "does not exist",
)

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

    def download_chunks(self, digests: list[str], destination_dir: Path) -> dict[str, Path]: ...


def _utcnow() -> datetime:
    return shanghai_now()


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


def _remote_path_is_missing(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in _REMOTE_MISSING_MARKERS)


def _load_pem_bytes(path: Path) -> bytes:
    if not path.exists():
        raise ValidationError(f"Backup credential file not found: {path}")
    return path.read_bytes()


def _fingerprint_public_key(raw_public_bytes: bytes) -> str:
    return hashlib.sha256(raw_public_bytes).hexdigest()


def _as_shanghai(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return normalize_shanghai_datetime(value)


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


def _decrypt_remote_recovery_keyring(keyring: dict[str, Any], *, passphrase: str) -> list[tuple[str, str, bytes, str]]:
    entries: list[tuple[str, str, bytes, str]] = []
    for item in keyring.get("keys") or []:
        fingerprint = str(item.get("secrets_fingerprint") or "")
        public_pem = str(item.get("secrets_public_pem") or "")
        encrypted_payload = item.get("encrypted_private_payload") or {}
        status = str(item.get("status") or "archived")
        if not fingerprint or not public_pem or not encrypted_payload:
            continue
        try:
            private_pem = _decrypt_private_key_from_escrow(encrypted_payload, passphrase=passphrase)
            public_key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
            if not isinstance(public_key, x25519.X25519PublicKey):
                continue
            if _fingerprint_public_key(public_key.public_bytes_raw()) != fingerprint:
                continue
            private_key = serialization.load_pem_private_key(private_pem, password=None)
            if not isinstance(private_key, x25519.X25519PrivateKey):
                continue
        except Exception:
            continue
        entries.append((status, fingerprint, private_pem, public_pem))
    if not entries:
        raise ValidationError("恢复密码不正确，无法解开远端恢复钥匙包。")
    return entries


def _install_remote_recovery_keyring(keyring: dict[str, Any], *, passphrase: str, credential_ref: str) -> list[str]:
    entries = _decrypt_remote_recovery_keyring(keyring, passphrase=passphrase)
    active_entry = next((entry for entry in entries if entry[0] == "active"), entries[0])
    key_dir = _credential_dir(credential_ref)
    key_dir.mkdir(parents=True, exist_ok=True)
    fingerprints: list[str] = []
    for status, fingerprint, private_pem, public_pem in entries:
        fingerprints.append(fingerprint)
        if (status, fingerprint, private_pem, public_pem) == active_entry:
            private_path = _current_private_key_path(credential_ref)
            public_path = _current_public_key_path(credential_ref)
        else:
            archive_key_dir = _archive_key_dir(credential_ref, fingerprint)
            archive_key_dir.mkdir(parents=True, exist_ok=True)
            private_path = _archive_private_key_path(credential_ref, fingerprint)
            public_path = _archive_public_key_path(credential_ref, fingerprint)
        private_path.write_bytes(private_pem)
        os.chmod(private_path, 0o600)
        public_path.write_text(public_pem, encoding="utf-8")
        os.chmod(public_path, 0o644)
    return sorted(set(fingerprints))


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


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _backup_ssh_dir() -> Path:
    return get_settings().data_dir / ".ssh"


def _backup_ssh_private_key_path() -> Path:
    return _backup_ssh_dir() / BACKUP_BOOTSTRAP_SSH_KEY_NAME


def _backup_ssh_public_key_path() -> Path:
    return _backup_ssh_dir() / f"{BACKUP_BOOTSTRAP_SSH_KEY_NAME}.pub"


def _backup_ssh_config_path() -> Path:
    return _backup_ssh_dir() / "config"


def _backup_ssh_known_hosts_path() -> Path:
    return _backup_ssh_dir() / "known_hosts"


def backup_remote_cleanup_command() -> str:
    return "sudo bash -c " + shlex.quote(
        "set -euo pipefail\n"
        f"userdel -r {BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME} >/dev/null 2>&1 || true\n"
        f"rm -rf {BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH}\n"
        'echo "Serino backup user and backup data have been removed."'
    )


def _local_repo_id(*, site_slug: str, credential_ref: str, recovery_key_fingerprint: str) -> str:
    payload = f"{site_slug}:{credential_ref}:{recovery_key_fingerprint}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _repo_identity_payload(config, credentials: BackupCredentialBundle) -> dict[str, Any]:
    repo_id = _local_repo_id(
        site_slug=str(config.site_slug),
        credential_ref=str(config.credential_ref),
        recovery_key_fingerprint=credentials.secrets_fingerprint,
    )
    return {
        "version": BACKUP_REPO_IDENTITY_VERSION,
        "repo_id": repo_id,
        "site_slug": str(config.site_slug),
        "credential_ref": str(config.credential_ref),
        "recovery_key_fingerprint": credentials.secrets_fingerprint,
        "created_at": _utcnow().isoformat(),
    }


def _remote_recovery_keyring_payload(session: Session, config) -> dict[str, Any]:
    credential_ref = str(config.credential_ref)
    keys: list[dict[str, Any]] = []
    for recovery_key in repo.list_backup_recovery_keys(session, credential_ref=credential_ref):
        keys.append(
            {
                "status": recovery_key.status,
                "secrets_fingerprint": recovery_key.secrets_fingerprint,
                "secrets_public_pem": recovery_key.secrets_public_pem,
                "encrypted_private_payload": copy.deepcopy(recovery_key.encrypted_private_payload or {}),
                "archived_at": recovery_key.archived_at.isoformat() if recovery_key.archived_at else None,
                "last_exported_at": recovery_key.last_exported_at.isoformat()
                if recovery_key.last_exported_at
                else None,
            }
        )
    if not keys:
        raise ValidationError("请先设置恢复密码，然后再创建备份。")
    return {
        "version": 1,
        "site_slug": str(config.site_slug),
        "credential_ref": credential_ref,
        "created_at": _utcnow().isoformat(),
        "keys": keys,
    }


def _repo_ids_from_keyring(keyring: dict[str, Any], *, site_slug: str, credential_ref: str) -> set[str]:
    repo_ids: set[str] = set()
    for item in keyring.get("keys") or []:
        fingerprint = str(item.get("secrets_fingerprint") or "").strip()
        if not fingerprint:
            continue
        repo_ids.add(
            _local_repo_id(
                site_slug=site_slug,
                credential_ref=credential_ref,
                recovery_key_fingerprint=fingerprint,
            )
        )
    return repo_ids


def _active_local_repo_id(session: Session, *, site_slug: str, credential_ref: str | None) -> str | None:
    if not credential_ref:
        return None
    active = repo.get_active_backup_recovery_key(session, credential_ref=credential_ref)
    if active is None:
        return None
    return _local_repo_id(
        site_slug=site_slug,
        credential_ref=credential_ref,
        recovery_key_fingerprint=active.secrets_fingerprint,
    )


def _accepted_local_repo_ids(session: Session, *, site_slug: str, credential_ref: str | None) -> set[str]:
    if not credential_ref:
        return set()
    ids: set[str] = set()
    for recovery_key in repo.list_backup_recovery_keys(session, credential_ref=credential_ref):
        if not recovery_key.secrets_fingerprint:
            continue
        ids.add(
            _local_repo_id(
                site_slug=site_slug,
                credential_ref=credential_ref,
                recovery_key_fingerprint=recovery_key.secrets_fingerprint,
            )
        )
    return ids


def _accepted_runtime_repo_ids(*, site_slug: str, credential_ref: str | None) -> set[str]:
    if not credential_ref:
        return set()
    ids: set[str] = set()
    for _status, fingerprint, _private_pem, _public_pem in _iter_runtime_key_material(credential_ref):
        ids.add(
            _local_repo_id(
                site_slug=site_slug,
                credential_ref=credential_ref,
                recovery_key_fingerprint=fingerprint,
            )
        )
    return ids


def _fingerprint_openssh_public_key(public_key: str) -> str:
    parts = public_key.strip().split()
    try:
        raw_key = base64.b64decode(parts[1]) if len(parts) >= 2 else public_key.encode("utf-8")
    except Exception:
        raw_key = public_key.encode("utf-8")
    digest = base64.b64encode(hashlib.sha256(raw_key).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"


def ensure_backup_ssh_keypair() -> tuple[str, str]:
    ssh_dir = _backup_ssh_dir()
    private_path = _backup_ssh_private_key_path()
    public_path = _backup_ssh_public_key_path()
    ssh_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(ssh_dir, 0o700)

    if not private_path.exists():
        proc = subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                str(private_path),
                "-N",
                "",
                "-C",
                "serino-backup",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise ValidationError(proc.stderr.strip() or "Failed to generate backup SSH key")
    elif not public_path.exists():
        proc = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(private_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise ValidationError(proc.stderr.strip() or "Failed to derive backup SSH public key")
        public_path.write_text(proc.stdout.strip() + "\n", encoding="utf-8")

    if not public_path.exists():
        raise ValidationError("Backup SSH public key was not generated")
    os.chmod(private_path, 0o600)
    os.chmod(public_path, 0o644)
    public_key = public_path.read_text(encoding="utf-8").strip()
    if not public_key.startswith(("ssh-ed25519 ", "ecdsa-", "ssh-rsa ")):
        raise ValidationError("Backup SSH public key has an unsupported format")
    return public_key, _fingerprint_openssh_public_key(public_key)


def _normalize_bootstrap_host(remote_host: str) -> tuple[str, int | None]:
    value = remote_host.strip()
    parsed_port: int | None = None
    if "://" in value:
        parsed = urlparse(value)
        value = parsed.hostname or ""
        parsed_port = parsed.port
    elif value.count(":") == 1 and value.rsplit(":", 1)[1].isdigit():
        value, raw_port = value.rsplit(":", 1)
        parsed_port = int(raw_port)
    value = value.strip().rstrip(".")
    if not value or _SSH_HOST_UNSAFE_RE.search(value):
        raise ValidationError("请填写备份机 IPv4 地址或域名，不要包含用户名、路径或空格。")
    if _SFTP_UNSAFE_RE.search(value):
        raise ValidationError("Backup host contains unsafe characters")
    return value, parsed_port


def _normalize_bootstrap_username(remote_username: str) -> str:
    value = remote_username.strip() or BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME
    if not _SSH_NAME_RE.match(value):
        raise ValidationError("备份机用户名只能包含字母、数字、点、下划线或短横线。")
    return value


def _normalize_bootstrap_path(remote_path: str) -> str:
    value = remote_path.strip() or BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH
    if _SFTP_UNSAFE_RE.search(value):
        raise ValidationError("Backup path contains unsafe characters")
    if not value.startswith("/"):
        raise ValidationError("备份目录必须是绝对路径，例如 /srv/serino-backups。")
    return value.rstrip("/") or "/"


def _normalize_public_base_url(public_base_url: str | None = None) -> str:
    value = (public_base_url or get_settings().site_url or "").strip().rstrip("/")
    if not value:
        value = "http://localhost:8000"
    return value


def _bootstrap_setup_url(*, token: str, public_base_url: str | None = None) -> str:
    return f"{_normalize_public_base_url(public_base_url)}/api/v1/backup/setup/{token}.sh"


def _bootstrap_result_url(*, token: str, public_base_url: str | None = None) -> str:
    return f"{_normalize_public_base_url(public_base_url)}/api/v1/backup/setup/{token}/result"


def _bootstrap_setup_command(*, token: str, public_base_url: str | None = None) -> str:
    return f"curl -fsSL {shlex.quote(_bootstrap_setup_url(token=token, public_base_url=public_base_url))} | sudo bash"


def _write_backup_ssh_config(*, remote_host: str, remote_port: int, remote_username: str) -> None:
    ssh_dir = _backup_ssh_dir()
    ssh_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(ssh_dir, 0o700)
    config_path = _backup_ssh_config_path()
    private_path = _backup_ssh_private_key_path()
    known_hosts_path = _backup_ssh_known_hosts_path()
    marker = f"SERINO BACKUP {remote_host}:{remote_port}:{remote_username}"
    begin = f"# BEGIN {marker}"
    end = f"# END {marker}"
    block = "\n".join(
        [
            begin,
            f"Host {remote_host}",
            f"  HostName {remote_host}",
            f"  User {remote_username}",
            f"  Port {remote_port}",
            f"  IdentityFile {private_path}",
            "  IdentitiesOnly yes",
            "  StrictHostKeyChecking accept-new",
            f"  UserKnownHostsFile {known_hosts_path}",
            end,
            "",
        ]
    )
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    lines = existing.splitlines()
    next_lines: list[str] = []
    skipping = False
    for line in lines:
        if line == begin:
            skipping = True
            continue
        if skipping and line == end:
            skipping = False
            continue
        if not skipping:
            next_lines.append(line)
    content = "\n".join(line for line in next_lines if line is not None).rstrip()
    config_path.write_text((content + "\n\n" if content else "") + block, encoding="utf-8")
    os.chmod(config_path, 0o600)


def _claim_read(
    claim,
    *,
    token: str | None = None,
    public_base_url: str | None = None,
) -> BackupBootstrapClaimRead:
    return BackupBootstrapClaimRead(
        id=claim.id,
        status=claim.status,
        remote_host=claim.remote_host,
        remote_port=claim.remote_port,
        remote_path=claim.remote_path,
        remote_username=claim.remote_username,
        site_slug=claim.site_slug,
        credential_ref=claim.credential_ref,
        public_key_fingerprint=claim.public_key_fingerprint,
        expires_at=claim.expires_at,
        used_at=claim.used_at,
        completed_at=claim.completed_at,
        revoked_at=claim.revoked_at,
        last_error=claim.last_error,
        setup_url=_bootstrap_setup_url(token=token, public_base_url=public_base_url) if token else None,
        setup_command=_bootstrap_setup_command(token=token, public_base_url=public_base_url) if token else None,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def _expire_claim_if_needed(session: Session, claim) -> None:
    if claim.status in ("pending", "failed") and _utcnow() > normalize_shanghai_datetime(claim.expires_at):
        claim.status = "expired"
        claim.last_error = claim.last_error or "临时接入链接已过期。"
        session.commit()
        session.refresh(claim)


def create_backup_bootstrap_claim(
    session: Session,
    payload: BackupBootstrapClaimCreate,
    *,
    created_by_admin_id: str | None,
    public_base_url: str | None = None,
) -> BackupBootstrapClaimRead:
    host, parsed_port = _normalize_bootstrap_host(payload.remote_host)
    port = int(parsed_port or payload.remote_port or 22)
    username = BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME
    remote_path = BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH
    site_slug = payload.site_slug.strip() or get_settings().backup_sync_default_site_slug
    credential_ref = payload.credential_ref.strip() or BACKUP_BOOTSTRAP_DEFAULT_CREDENTIAL_REF
    public_key, fingerprint = ensure_backup_ssh_keypair()
    _write_backup_ssh_config(remote_host=host, remote_port=port, remote_username=username)

    now = _utcnow()
    for old in repo.list_pending_backup_bootstrap_claims_for_target(
        session,
        created_by_admin_id=created_by_admin_id,
        remote_host=host,
        remote_port=port,
        remote_username=username,
        remote_path=remote_path,
    ):
        old.status = "revoked"
        old.revoked_at = now
        old.last_error = "已生成新的临时接入命令，旧命令自动失效。"

    token = secrets.token_urlsafe(32)
    claim = repo.create_backup_bootstrap_claim(
        session,
        token_hash=_token_hash(token),
        status="pending",
        created_by_admin_id=created_by_admin_id,
        site_slug=site_slug,
        credential_ref=credential_ref,
        remote_host=host,
        remote_port=port,
        remote_username=username,
        remote_path=remote_path,
        public_key_pem=public_key,
        public_key_fingerprint=fingerprint,
        expires_at=now + timedelta(minutes=payload.ttl_minutes or BACKUP_BOOTSTRAP_DEFAULT_TTL_MINUTES),
        result_json={},
    )
    session.commit()
    session.refresh(claim)
    return _claim_read(claim, token=token, public_base_url=public_base_url)


def get_backup_bootstrap_claim(session: Session, claim_id: str) -> BackupBootstrapClaimRead:
    claim = repo.get_backup_bootstrap_claim(session, claim_id)
    if claim is None:
        raise ResourceNotFound("Backup bootstrap claim not found")
    _expire_claim_if_needed(session, claim)
    return _claim_read(claim)


def revoke_backup_bootstrap_claim(session: Session, claim_id: str) -> BackupBootstrapClaimRead:
    claim = repo.get_backup_bootstrap_claim(session, claim_id)
    if claim is None:
        raise ResourceNotFound("Backup bootstrap claim not found")
    _expire_claim_if_needed(session, claim)
    if claim.status in ("pending", "failed"):
        claim.status = "revoked"
        claim.revoked_at = _utcnow()
        claim.last_error = "已撤销临时接入命令。"
        session.commit()
        session.refresh(claim)
    return _claim_read(claim)


def _usable_claim_by_token(session: Session, token: str):
    claim = repo.get_backup_bootstrap_claim_by_token_hash(session, _token_hash(token))
    if claim is None:
        raise ResourceNotFound("Backup setup link not found")
    _expire_claim_if_needed(session, claim)
    if claim.status == "expired":
        raise StateConflict("Backup setup link has expired")
    if claim.status == "revoked":
        raise StateConflict("Backup setup link has been revoked")
    if claim.status == "succeeded":
        raise StateConflict("Backup setup link has already been used")
    return claim


def render_backup_bootstrap_script(
    session: Session,
    *,
    token: str,
    public_base_url: str | None = None,
) -> str:
    claim = _usable_claim_by_token(session, token)
    now = _utcnow()
    claim.used_at = claim.used_at or now
    session.commit()
    session.refresh(claim)
    return _render_backup_bootstrap_script(claim, token=token, public_base_url=public_base_url)


def register_backup_bootstrap_result(
    session: Session,
    *,
    token: str,
    payload: BackupBootstrapClaimResultWrite,
) -> BackupBootstrapClaimRead:
    claim = _usable_claim_by_token(session, token)
    now = _utcnow()
    message = (payload.message or "").strip()
    claim.result_json = {"status": payload.status, "message": message, "details": payload.details}
    if payload.status == "succeeded":
        claim.status = "succeeded"
        claim.completed_at = now
        claim.last_error = None
        _write_backup_ssh_config(
            remote_host=claim.remote_host,
            remote_port=claim.remote_port,
            remote_username=claim.remote_username,
        )
    else:
        claim.status = "failed"
        claim.last_error = message or "备份机脚本执行失败。"
    session.commit()
    session.refresh(claim)
    return _claim_read(claim)


def _render_backup_bootstrap_script(claim, *, token: str, public_base_url: str | None = None) -> str:
    result_url = _bootstrap_result_url(token=token, public_base_url=public_base_url)
    return f"""#!/usr/bin/env bash
set -Eeuo pipefail

CLAIM_RESULT_URL={shlex.quote(result_url)}
REMOTE_USER={shlex.quote(claim.remote_username)}
REMOTE_PATH={shlex.quote(claim.remote_path)}
PUBLIC_KEY={shlex.quote(claim.public_key_pem.strip())}
KEY_FINGERPRINT={shlex.quote(claim.public_key_fingerprint)}

REPORTED=0

json_escape() {{
  printf '%s' "$1" | sed 's/\\\\/\\\\\\\\/g; s/"/\\\\"/g'
}}

post_result() {{
  local status="$1"
  local message="$2"
  local escaped
  escaped="$(json_escape "$message")"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS -X POST "$CLAIM_RESULT_URL" \\
      -H 'Content-Type: application/json' \\
      --data "{{\\"status\\":\\"$status\\",\\"message\\":\\"$escaped\\"}}" >/dev/null 2>&1 || true
  fi
}}

fail() {{
  local message="$1"
  echo "ERROR: $message" >&2
  REPORTED=1
  post_result failed "$message"
  exit 1
}}

trap 'rc=$?; if [ "$rc" -ne 0 ] && [ "$REPORTED" != "1" ]; then post_result failed "setup script failed with exit code $rc"; fi' EXIT

[ "$(id -u)" -eq 0 ] || fail "please run this command with sudo"
command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v id >/dev/null 2>&1 || fail "id is required"
command -v getent >/dev/null 2>&1 || fail "getent is required"
command -v install >/dev/null 2>&1 || fail "install is required"
command -v awk >/dev/null 2>&1 || fail "awk is required"

if ! id "$REMOTE_USER" >/dev/null 2>&1; then
  if command -v useradd >/dev/null 2>&1; then
    useradd --system --create-home --shell /bin/sh "$REMOTE_USER"
  elif command -v adduser >/dev/null 2>&1; then
    adduser --system --home "/home/$REMOTE_USER" --shell /bin/sh "$REMOTE_USER"
  else
    fail "useradd or adduser is required"
  fi
fi

REMOTE_GROUP="$(id -gn "$REMOTE_USER")"
REMOTE_HOME="$(getent passwd "$REMOTE_USER" | awk -F: '{{print $6}}')"
[ -n "$REMOTE_HOME" ] || REMOTE_HOME="/home/$REMOTE_USER"

install -d -m 0700 -o "$REMOTE_USER" -g "$REMOTE_GROUP" "$REMOTE_HOME/.ssh"
install -d -m 0700 -o "$REMOTE_USER" -g "$REMOTE_GROUP" "$REMOTE_PATH"

AUTHORIZED_KEYS="$REMOTE_HOME/.ssh/authorized_keys"
TEMP_AUTH="$(mktemp)"
if [ -f "$AUTHORIZED_KEYS" ]; then
  awk '
    index($0, "# BEGIN SERINO BACKUP ") == 1 {{ skip = 1; next }}
    index($0, "# END SERINO BACKUP ") == 1 {{ skip = 0; next }}
    skip != 1 {{ print }}
  ' "$AUTHORIZED_KEYS" > "$TEMP_AUTH"
else
  : > "$TEMP_AUTH"
fi

{{
  printf '# BEGIN SERINO BACKUP %s\\n' "$KEY_FINGERPRINT"
  printf 'command="internal-sftp",no-pty,no-port-forwarding,no-X11-forwarding,no-agent-forwarding %s\\n' "$PUBLIC_KEY"
  printf '# END SERINO BACKUP %s\\n' "$KEY_FINGERPRINT"
}} >> "$TEMP_AUTH"

install -m 0600 -o "$REMOTE_USER" -g "$REMOTE_GROUP" "$TEMP_AUTH" "$AUTHORIZED_KEYS"
rm -f "$TEMP_AUTH"

REPORTED=1
post_result succeeded "备份机已成功连接"
cat <<'MESSAGE'
备份机已成功连接！
请您返回后台管理界面稍等片刻，那边正在检测...
MESSAGE
"""


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
        retention_days=config.retention_days,
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
        remote_path=BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH,
        remote_username=BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME,
        credential_ref=payload.credential_ref or "aerisun-backup-source",
        encrypt_runtime_data=bool(payload.encrypt_runtime_data),
        enabled=bool(payload.enabled),
        paused=bool(payload.paused),
        interval_minutes=max(int(payload.interval_minutes or settings.backup_sync_default_interval_minutes), 1),
        max_retries=max(int(payload.max_retries or 0), 0),
        retry_backoff_seconds=max(int(payload.retry_backoff_seconds or 300), 30),
        max_retention_count=max(int(payload.max_retention_count or 0), 0),
        retention_days=max(int(payload.retention_days or 0), 0),
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
            remote_path=BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH,
            remote_username=BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME,
            credential_ref=BACKUP_BOOTSTRAP_DEFAULT_CREDENTIAL_REF,
            encrypt_runtime_data=True,
            max_retries=3,
            retry_backoff_seconds=300,
            max_retention_count=settings.backup_sync_default_max_retention_count,
            retention_days=settings.backup_sync_default_retention_days,
        )
        session.commit()
        session.refresh(config)
    return config


def get_backup_sync_config(session: Session) -> BackupSyncConfig:
    return _config_read(get_or_create_backup_sync_config(session))


def _inspect_remote_history(session: Session, *, config, transport) -> dict[str, Any]:
    local_repo_id = _active_local_repo_id(
        session,
        site_slug=str(config.site_slug),
        credential_ref=str(config.credential_ref) if config.credential_ref else None,
    )
    accepted_repo_ids = _accepted_local_repo_ids(
        session,
        site_slug=str(config.site_slug),
        credential_ref=str(config.credential_ref) if config.credential_ref else None,
    )
    if not hasattr(transport, "fetch_repo_identity"):
        return {
            "remote_history_state": "unknown",
            "remote_history_summary": "备份机可连接，但当前传输层不支持仓库身份检测。",
            "remote_repo_id": None,
            "local_repo_id": local_repo_id,
        }
    identity = transport.fetch_repo_identity()
    if identity is None:
        return {
            "remote_history_state": "empty",
            "remote_history_summary": "备份机可连接，未发现历史备份。",
            "remote_repo_id": None,
            "local_repo_id": local_repo_id,
        }
    remote_repo_id = str(identity.get("repo_id") or "")
    if remote_repo_id and remote_repo_id in accepted_repo_ids:
        return {
            "remote_history_state": "current",
            "remote_history_summary": "发现当前站点的备份历史，可继续增量备份。",
            "remote_repo_id": remote_repo_id,
            "local_repo_id": local_repo_id,
        }
    return {
        "remote_history_state": "foreign",
        "remote_history_summary": "这台备份机上已有另一套备份历史。为避免数据混乱，不能直接写入。",
        "remote_repo_id": remote_repo_id or None,
        "local_repo_id": local_repo_id,
    }


def _history_from_identity(session: Session, *, config, identity: dict[str, Any] | None) -> dict[str, Any]:
    local_repo_id = _active_local_repo_id(
        session,
        site_slug=str(config.site_slug),
        credential_ref=str(config.credential_ref) if config.credential_ref else None,
    )
    accepted_repo_ids = _accepted_local_repo_ids(
        session,
        site_slug=str(config.site_slug),
        credential_ref=str(config.credential_ref) if config.credential_ref else None,
    )
    if identity is None:
        return {
            "remote_history_state": "empty",
            "remote_history_summary": "备份机可连接，未发现历史备份。",
            "remote_repo_id": None,
            "local_repo_id": local_repo_id,
        }
    remote_repo_id = str(identity.get("repo_id") or "")
    if remote_repo_id and remote_repo_id in accepted_repo_ids:
        return {
            "remote_history_state": "current",
            "remote_history_summary": "发现当前站点的备份历史，可继续增量备份。",
            "remote_repo_id": remote_repo_id,
            "local_repo_id": local_repo_id,
        }
    return {
        "remote_history_state": "foreign",
        "remote_history_summary": "这台备份机上已有另一套备份历史。为避免数据混乱，不能直接写入。",
        "remote_repo_id": remote_repo_id or None,
        "local_repo_id": local_repo_id,
    }


def probe_backup_machine_connection(session: Session, payload: BackupSyncConfigUpdate) -> BackupSyncConfigTestRead:
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
    connected = False
    identity: dict[str, Any] | None = None
    _error_message: str | None = None
    if hasattr(transport, "probe_repo_identity"):
        connected, identity, _error_message = transport.probe_repo_identity(timeout_seconds=3)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    if not connected:
        summary = "还没有接入这台备份机。请生成临时命令，并在备份机上执行。"
        return BackupSyncConfigTestRead(
            ok=False,
            summary=summary,
            latency_ms=latency_ms,
            remote_path_preview=str(config.remote_path or ""),
            recovery_key_ready=recovery_ready,
            recovery_key_acknowledged=recovery_acknowledged,
            remote_history_state="unreachable",
            remote_history_summary=summary,
        )
    history = _history_from_identity(session, config=config, identity=identity)
    return BackupSyncConfigTestRead(
        ok=True,
        summary=history["remote_history_summary"] or "备份机可连接。",
        latency_ms=latency_ms,
        remote_path_preview=str(config.remote_path or ""),
        recovery_key_ready=recovery_ready,
        recovery_key_acknowledged=recovery_acknowledged,
        **history,
    )


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
        transport.begin_session(timeout_seconds=BACKUP_SYNC_CONFIG_TEST_TIMEOUT_SECONDS)
        transport.probe_write_access(timeout_seconds=BACKUP_SYNC_CONFIG_TEST_TIMEOUT_SECONDS)
    except ValidationError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return BackupSyncConfigTestRead(
            ok=False,
            summary=str(exc),
            latency_ms=latency_ms,
            remote_path_preview=str(config.remote_path or ""),
            recovery_key_ready=recovery_ready,
            recovery_key_acknowledged=recovery_acknowledged,
            remote_history_state="unreachable",
            remote_history_summary="无法使用 serino-backup 连接备份机，需要先执行临时接入命令。",
        )
    history = _inspect_remote_history(session, config=config, transport=transport)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return BackupSyncConfigTestRead(
        ok=True,
        summary=history["remote_history_summary"] or "SFTP 连接正常，远端目录可写。",
        latency_ms=latency_ms,
        remote_path_preview=str(config.remote_path or ""),
        recovery_key_ready=recovery_ready,
        recovery_key_acknowledged=recovery_acknowledged,
        **history,
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
    config.remote_path = BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH
    config.remote_username = BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME
    config.credential_ref = payload.credential_ref
    config.encrypt_runtime_data = bool(payload.encrypt_runtime_data)
    config.max_retries = max(payload.max_retries, 0)
    config.retry_backoff_seconds = max(payload.retry_backoff_seconds, 30)
    config.max_retention_count = max(payload.max_retention_count, 0)
    config.retention_days = max(payload.retention_days, 0)
    _validate_config(config)
    active_recovery_key = repo.get_active_backup_recovery_key(session, credential_ref=str(config.credential_ref))
    if active_recovery_key is None:
        raise ValidationError("请先设置恢复密码，然后再保存备份配置。")
    if active_recovery_key.acknowledged_at is None:
        raise ValidationError("请先确认恢复密码，然后再保存备份配置。")
    retention_cleanup_needed = _retention_cleanup_required(session, config)
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
    if retention_cleanup_needed:
        schedule_backup_retention_cleanup()
    return _config_read(config)


def overwrite_remote_backup_history(session: Session, payload: BackupSyncConfigUpdate) -> BackupSyncConfigTestRead:
    update_backup_sync_config(session, payload)
    config = get_or_create_backup_sync_config(session)
    _validate_config(config)
    active_recovery_key = repo.get_active_backup_recovery_key(session, credential_ref=str(config.credential_ref))
    if active_recovery_key is None or active_recovery_key.acknowledged_at is None:
        raise ValidationError("请先设置恢复密码，然后再覆盖远端历史。")
    credentials = load_backup_credentials(str(config.credential_ref))
    transport = build_transport(config, credentials)
    started_at = time.perf_counter()
    transport.begin_session()
    remote_repo_id: str | None = None
    if hasattr(transport, "fetch_repo_identity"):
        identity = transport.fetch_repo_identity()
        if identity is not None:
            remote_repo_id = str(identity.get("repo_id") or "") or None
    if hasattr(transport, "archive_current_repo"):
        transport.archive_current_repo(remote_repo_id=remote_repo_id)
    if hasattr(transport, "write_repo_identity"):
        transport.write_repo_identity(_repo_identity_payload(config, credentials))
    repo.clear_backup_history_records(session, job_name=BACKUP_JOB_NAME)
    session.commit()
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    local_repo_id = _local_repo_id(
        site_slug=str(config.site_slug),
        credential_ref=str(config.credential_ref),
        recovery_key_fingerprint=credentials.secrets_fingerprint,
    )
    return BackupSyncConfigTestRead(
        ok=True,
        summary="已归档旧备份历史，并为当前站点初始化新的备份历史。",
        latency_ms=latency_ms,
        remote_path_preview=str(config.remote_path or BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH),
        recovery_key_ready=True,
        recovery_key_acknowledged=True,
        remote_history_state="current",
        remote_history_summary="当前站点的新备份历史已准备好。",
        remote_repo_id=local_repo_id,
        local_repo_id=local_repo_id,
    )


def _remote_history_transport(config) -> BackupTransport:
    return build_transport(config, None)  # type: ignore[arg-type]


def _require_remote_recovery_keyring(transport: BackupTransport) -> dict[str, Any]:
    if not hasattr(transport, "fetch_recovery_keyring"):
        raise ValidationError("当前传输层不支持灾后恢复钥匙包读取。")
    keyring = transport.fetch_recovery_keyring()
    if keyring is None:
        raise ValidationError("远端备份历史缺少恢复钥匙包。请在原服务升级后重新创建一次备份，再进行灾后恢复。")
    return keyring


def _resolve_remote_recovery_keyring(
    session: Session,
    *,
    config,
    transport: BackupTransport,
    passphrase: str,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        return _require_remote_recovery_keyring(transport)
    except ValidationError as exc:
        if "缺少恢复钥匙包" not in str(exc):
            raise
    try:
        keyring = _remote_recovery_keyring_payload(session, config)
    except ValidationError as exc:
        if "请先设置恢复密码" in str(exc):
            raise ValidationError(
                "远端备份历史缺少恢复钥匙包，当前机器也没有这批备份的恢复钥匙记录，"
                "不能仅凭密码恢复。请在创建这批备份的原服务升级后重新创建一次备份，"
                "或选择已经包含恢复钥匙包的备份历史。"
            ) from exc
        raise
    identity_payload = identity
    if identity_payload is None and hasattr(transport, "fetch_repo_identity"):
        identity_payload = transport.fetch_repo_identity()
    remote_repo_id = str((identity_payload or {}).get("repo_id") or "").strip()
    if remote_repo_id:
        local_repo_ids = _repo_ids_from_keyring(
            keyring,
            site_slug=str(config.site_slug),
            credential_ref=str(config.credential_ref),
        )
        if remote_repo_id not in local_repo_ids:
            raise ValidationError(
                "远端备份历史缺少恢复钥匙包，且本机恢复钥匙与远端历史不匹配。请回到创建这批备份的原服务升级后重新创建一次备份。"
            )
    _decrypt_remote_recovery_keyring(keyring, passphrase=passphrase)
    if not hasattr(transport, "write_recovery_keyring"):
        raise ValidationError("当前传输层不支持灾后恢复钥匙包写入。")
    transport.write_recovery_keyring(keyring)
    return keyring


def _parse_backup_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _remote_history_commit_read(item: dict[str, Any]) -> BackupRemoteHistoryCommitRead:
    return BackupRemoteHistoryCommitRead(
        id=str(item["commit_id"]),
        remote_commit_id=str(item.get("remote_commit_id") or item["commit_id"]),
        manifest_digest=str(item["manifest_digest"]),
        backup_path=item.get("backup_path"),
        created_at=_parse_backup_datetime(item["created_at"]),
    )


def preview_remote_backup_history_import(
    session: Session, payload: BackupRemoteHistoryImportWrite
) -> BackupRemoteHistoryImportPreviewRead:
    config = _config_object_from_payload(payload.config)
    _validate_config(config)
    transport = _remote_history_transport(config)
    identity = transport.fetch_repo_identity() if hasattr(transport, "fetch_repo_identity") else None
    keyring = _resolve_remote_recovery_keyring(
        session,
        config=config,
        transport=transport,
        passphrase=payload.passphrase,
        identity=identity,
    )
    key_fingerprints = [
        fingerprint
        for _status, fingerprint, _private_pem, _public_pem in _decrypt_remote_recovery_keyring(
            keyring, passphrase=payload.passphrase
        )
    ]
    commits = [_remote_history_commit_read(item) for item in transport.list_commits()]
    return BackupRemoteHistoryImportPreviewRead(
        remote_repo_id=str(identity.get("repo_id")) if identity else None,
        site_slug=str(keyring.get("site_slug") or config.site_slug),
        credential_ref=str(keyring.get("credential_ref") or config.credential_ref),
        key_fingerprints=sorted(set(key_fingerprints)),
        commits=commits,
    )


def _remote_backup_commit_restore_record(
    config, commit_payload: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    created_at = _parse_backup_datetime(commit_payload.get("created_at") or manifest.get("created_at"))
    return {
        "id": str(commit_payload.get("commit_id") or manifest["commit_id"]),
        "transport": str(manifest.get("transport") or config.transport_mode),
        "trigger_kind": str(manifest.get("trigger_kind") or "remote-history-import"),
        "site_slug": str(manifest.get("site_slug") or config.site_slug),
        "remote_commit_id": str(
            commit_payload.get("remote_commit_id") or commit_payload.get("commit_id") or manifest["commit_id"]
        ),
        "manifest_digest": str(commit_payload["manifest_digest"]),
        "backup_path": commit_payload.get("backup_path"),
        "datasets": copy.deepcopy(manifest.get("datasets") or {}),
        "stats_json": {},
        "snapshot_started_at": _parse_backup_datetime(manifest.get("created_at") or created_at),
        "snapshot_finished_at": created_at,
        "restored_at": None,
        "created_at": created_at,
        "updated_at": created_at,
    }


def restore_remote_backup_history(session: Session, payload: BackupRemoteHistoryRestoreWrite) -> BackupCommitRead:
    config = _config_object_from_payload(payload.config)
    _validate_config(config)
    transport = _remote_history_transport(config)
    keyring = _resolve_remote_recovery_keyring(
        session,
        config=config,
        transport=transport,
        passphrase=payload.passphrase,
    )
    credential_ref = str(keyring.get("credential_ref") or config.credential_ref)
    _install_remote_recovery_keyring(keyring, passphrase=payload.passphrase, credential_ref=credential_ref)
    credentials = load_backup_credentials(credential_ref)
    commit_payload = transport.fetch_commit(payload.commit_id)
    manifest = transport.fetch_manifest(commit_payload["manifest_digest"])
    commit_record = _remote_backup_commit_restore_record(config, commit_payload, manifest)
    response = BackupCommitRead.model_validate(SimpleNamespace(**commit_record))
    session.close()
    _restore_from_manifest(manifest, transport, credentials)
    restored_at = _utcnow()
    try:
        with get_session_factory()() as restored_session:
            _repair_restored_backup_runtime_state(restored_session, restored_at=restored_at)
            restored_commit = repo.get_backup_commit(restored_session, commit_record["id"])
            if restored_commit is None:
                restored_commit = repo.create_backup_commit(restored_session, **commit_record)
            restored_commit.restored_at = restored_at
            restored_session.commit()
    except Exception:
        logger.warning("Failed to persist remote backup import restore marker", exc_info=True)
    return response.model_copy(update={"restored_at": restored_at})


def reset_backup_sync_system(session: Session) -> BackupSystemResetRead:
    config = get_or_create_backup_sync_config(session)
    credential_ref = str(config.credential_ref or BACKUP_BOOTSTRAP_DEFAULT_CREDENTIAL_REF)
    repo.reset_backup_sync_records(session, credential_ref=credential_ref, job_name=BACKUP_JOB_NAME)
    config.enabled = False
    config.paused = False
    config.interval_minutes = get_settings().backup_sync_default_interval_minutes
    config.transport_mode = "sftp"
    config.site_slug = get_settings().backup_sync_default_site_slug
    config.remote_host = ""
    config.remote_port = 22
    config.remote_path = BACKUP_BOOTSTRAP_DEFAULT_REMOTE_PATH
    config.remote_username = BACKUP_BOOTSTRAP_DEFAULT_REMOTE_USERNAME
    config.credential_ref = BACKUP_BOOTSTRAP_DEFAULT_CREDENTIAL_REF
    config.encrypt_runtime_data = True
    config.max_retries = 3
    config.retry_backoff_seconds = 300
    config.max_retention_count = get_settings().backup_sync_default_max_retention_count
    config.retention_days = get_settings().backup_sync_default_retention_days
    config.last_scheduled_at = None
    config.last_synced_at = None
    config.last_error = None
    shutil.rmtree(_credential_dir(credential_ref), ignore_errors=True)
    for path in (_backup_ssh_private_key_path(), _backup_ssh_public_key_path(), _backup_ssh_config_path()):
        path.unlink(missing_ok=True)
    session.commit()
    session.refresh(config)
    return BackupSystemResetRead(config=_config_read(config), remote_cleanup_command=backup_remote_cleanup_command())


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
    runtime_files = [relative for _path, relative in _iter_runtime_files(settings)]
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
        "runtime_files": {
            "file_count": len(runtime_files),
            "paths_digest": _sha256_bytes("\n".join(runtime_files).encode("utf-8")),
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
    queue_item_id = queue_item.id
    dispatch_backup_sync()
    session.expire_all()
    refreshed = repo.get_backup_queue_item(session, queue_item_id)
    run = next(
        (item for item in repo.list_sync_runs(session) if item.queue_item_id == queue_item_id),
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
            last_reference = _as_shanghai(config.last_scheduled_at or config.last_synced_at or config.created_at)
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


def _chunk_digests_from_commit(commit) -> set[str]:
    return set(_manifest_chunk_digests({"datasets": copy.deepcopy(commit.datasets or {})}))


def _delete_remote_manifests(transport: BackupTransport, digests: set[str]) -> bool:
    if not digests:
        return True
    if hasattr(transport, "delete_manifests"):
        try:
            transport.delete_manifests(sorted(digests))
            return True
        except Exception:
            logger.warning("Failed to delete remote backup manifests in batch", exc_info=True)
    if not hasattr(transport, "delete_manifest"):
        return False
    ok = True
    for digest in sorted(digests):
        try:
            transport.delete_manifest(digest)
        except Exception:
            ok = False
            logger.warning("Failed to delete remote backup manifest %s", digest, exc_info=True)
    return ok


def _delete_remote_chunks(transport: BackupTransport, digests: set[str]) -> bool:
    if not digests:
        return True
    if hasattr(transport, "delete_chunks"):
        try:
            transport.delete_chunks(sorted(digests))
            return True
        except Exception:
            logger.warning("Failed to delete remote backup chunks in batch", exc_info=True)
    if not hasattr(transport, "delete_chunk"):
        return False
    ok = True
    for digest in sorted(digests):
        try:
            transport.delete_chunk(digest)
        except Exception:
            ok = False
            logger.warning("Failed to delete remote backup chunk %s", digest, exc_info=True)
    return ok


def _delete_remote_commit_index(transport: BackupTransport, commit) -> bool:
    if not hasattr(transport, "delete_commit"):
        logger.warning("Backup transport cannot delete remote commits; retention cleanup skipped for %s", commit.id)
        return False
    try:
        transport.delete_commit(
            commit.remote_commit_id,
            created_at=commit.created_at.isoformat(),
            backup_path=commit.backup_path,
        )
        return True
    except Exception:
        logger.warning("Failed to delete remote commit %s; local backup history kept", commit.id, exc_info=True)
        return False


def _cleanup_unreferenced_remote_objects(
    transport: BackupTransport,
    *,
    cleanup_candidates: list[Any],
    protected_commits: list[Any],
) -> bool:
    protected_manifest_digests = {commit.manifest_digest for commit in protected_commits}
    protected_chunk_digests: set[str] = set()
    for commit in protected_commits:
        protected_chunk_digests.update(_chunk_digests_from_commit(commit))
    stale_manifest_digests = {
        commit.manifest_digest
        for commit in cleanup_candidates
        if commit.manifest_digest not in protected_manifest_digests
    }
    stale_chunk_digests: set[str] = set()
    for commit in cleanup_candidates:
        stale_chunk_digests.update(_chunk_digests_from_commit(commit))
    stale_chunk_digests.difference_update(protected_chunk_digests)
    manifests_removed = _delete_remote_manifests(transport, stale_manifest_digests)
    chunks_removed = _delete_remote_chunks(transport, stale_chunk_digests)
    return manifests_removed and chunks_removed


def _retention_cutoff(config) -> datetime | None:
    retention_days = getattr(config, "retention_days", 0)
    if not retention_days or retention_days <= 0:
        return None
    return _utcnow() - timedelta(days=int(retention_days))


def _retention_removal_ids(visible_commits: list[Any], *, max_count: int, cutoff: datetime | None) -> set[str]:
    removal_ids: set[str] = set()
    if max_count > 0:
        removal_ids.update(str(commit.id) for commit in visible_commits[max_count:])
    if cutoff is not None:
        normalized_cutoff = _as_shanghai(cutoff)
        for commit in visible_commits:
            created_at = _as_shanghai(commit.created_at)
            if created_at is not None and normalized_cutoff is not None and created_at < normalized_cutoff:
                removal_ids.add(str(commit.id))
    return removal_ids


def _retention_cleanup_required(session: Session, config) -> bool:
    max_count = max(int(getattr(config, "max_retention_count", 0) or 0), 0)
    cutoff = _retention_cutoff(config)
    all_records = repo.list_backup_commits(session, include_retention_tombstones=True)
    visible_commits = [commit for commit in all_records if commit.trigger_kind != BACKUP_RETENTION_TOMBSTONE_TRIGGER]
    tombstones = [commit for commit in all_records if commit.trigger_kind == BACKUP_RETENTION_TOMBSTONE_TRIGGER]
    if tombstones:
        return True
    if max_count <= 0 and cutoff is None:
        return False
    return bool(_retention_removal_ids(visible_commits, max_count=max_count, cutoff=cutoff))


def _retention_config_snapshot(config) -> SimpleNamespace:
    return SimpleNamespace(
        transport_mode=config.transport_mode,
        site_slug=config.site_slug,
        remote_host=config.remote_host,
        remote_port=config.remote_port,
        remote_path=config.remote_path,
        remote_username=config.remote_username,
        credential_ref=config.credential_ref,
        max_retention_count=config.max_retention_count,
        retention_days=config.retention_days,
    )


def schedule_backup_retention_cleanup() -> None:
    worker = threading.Thread(
        target=_run_backup_retention_cleanup_safely,
        name="backup-retention-cleanup",
        daemon=True,
    )
    worker.start()


def _run_backup_retention_cleanup_safely() -> None:
    try:
        _run_backup_retention_cleanup()
    except Exception:
        logger.warning("Retention cleanup after config update failed (non-fatal)", exc_info=True)


def _run_backup_retention_cleanup() -> None:
    with _retention_cleanup_lock:
        session_factory = get_session_factory()
        with session_factory() as session:
            config = repo.get_backup_target_config(session)
            if config is None:
                return
            _validate_config(config)
            if not _retention_cleanup_required(session, config):
                return
            cleanup_config = _retention_config_snapshot(config)
        credentials = load_backup_credentials(str(cleanup_config.credential_ref))
        transport = build_transport(cleanup_config, credentials)
        transport.begin_session()
        _enforce_retention(cleanup_config, transport)


def _enforce_retention(config, transport: BackupTransport) -> None:
    """Delete backup commits and remote objects outside configured retention limits."""
    max_count = max(int(getattr(config, "max_retention_count", 0) or 0), 0)
    cutoff = _retention_cutoff(config)
    session_factory = get_session_factory()
    with session_factory() as session:
        all_records = repo.list_backup_commits(session, include_retention_tombstones=True)
        visible_commits = [
            commit for commit in all_records if commit.trigger_kind != BACKUP_RETENTION_TOMBSTONE_TRIGGER
        ]
        tombstones = [commit for commit in all_records if commit.trigger_kind == BACKUP_RETENTION_TOMBSTONE_TRIGGER]
        removal_ids = _retention_removal_ids(visible_commits, max_count=max_count, cutoff=cutoff)
        if not removal_ids and not tombstones:
            return
        to_remove = [commit for commit in visible_commits if str(commit.id) in removal_ids]
        retained = [commit for commit in visible_commits if str(commit.id) not in removal_ids]
        removed: list[Any] = []
        protected = list(retained)
        for commit in to_remove:
            if _delete_remote_commit_index(transport, commit):
                commit.trigger_kind = BACKUP_RETENTION_TOMBSTONE_TRIGGER
                commit.backup_path = None
                removed.append(commit)
            else:
                protected.append(commit)
        cleanup_candidates = [*tombstones, *removed]
        if not cleanup_candidates:
            return

        if _cleanup_unreferenced_remote_objects(
            transport,
            cleanup_candidates=cleanup_candidates,
            protected_commits=protected,
        ):
            for commit in cleanup_candidates:
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
        recovery_keyring = _remote_recovery_keyring_payload(session, config)

    prepared = prepare_run_artifacts(credentials, encrypt_runtime_data=bool(config.encrypt_runtime_data))
    uploaded_chunk_digests: list[str] = []
    try:
        transport = build_transport(config, credentials)
        transport.begin_session()
        _ensure_remote_repo_identity(config, credentials, transport)
        if hasattr(transport, "write_recovery_keyring"):
            transport.write_recovery_keyring(recovery_keyring)
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
            with session_factory() as session:
                current_config = repo.get_backup_target_config(session)
                if current_config is not None and _retention_cleanup_required(session, current_config):
                    schedule_backup_retention_cleanup()
        except Exception:
            logger.warning("Retention cleanup scheduling failed (non-fatal)", exc_info=True)
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

    runtime_files_tar = temp_dir / "runtime-files.tar"
    _tar_runtime_files(settings, runtime_files_tar)
    runtime_files_zst = temp_dir / "runtime-files.tar.zst"
    _zstd_compress_file(runtime_files_tar, runtime_files_zst)
    runtime_files_payload_path, runtime_files_encryption = _prepare_runtime_payload(
        runtime_files_zst,
        temp_dir=temp_dir,
        temp_name="runtime-files.tar.zst.enc",
        public_key=runtime_public_key,
        aad=b"datasets/runtime-files.tar.zst",
    )
    files.append(
        _prepare_file(
            runtime_files_payload_path,
            "datasets/runtime-files.tar.zst",
            chunk_root=temp_dir,
            dataset_kind="runtime_files",
            compression="zstd",
            encryption=runtime_files_encryption,
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


def _sqlite_sidecar_paths(target: Path) -> tuple[Path, Path]:
    return (Path(f"{target}-wal"), Path(f"{target}-shm"))


def _atomic_sqlite_replace(source: Path, target: Path) -> None:
    for sidecar in _sqlite_sidecar_paths(target):
        sidecar.unlink(missing_ok=True)
    _atomic_file_replace(source, target)
    for sidecar in _sqlite_sidecar_paths(target):
        sidecar.unlink(missing_ok=True)


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


def _runtime_relative_prefix(settings, path: Path) -> str | None:
    try:
        return path.expanduser().resolve().relative_to(settings.data_dir.expanduser().resolve()).as_posix()
    except ValueError:
        return None


def _runtime_relative_is_excluded(settings, relative: str) -> bool:
    relative_path = PurePosixPath(relative)
    parts = relative_path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return True
    if parts[0].startswith("."):
        return True

    excluded_dirs = (
        settings.media_dir,
        settings.secrets_dir,
        settings.backup_sync_tmp_dir,
        settings.data_dir / "automation" / "packs",
        settings.data_dir / ".ssh",
    )
    for excluded_dir in excluded_dirs:
        prefix = _runtime_relative_prefix(settings, excluded_dir)
        if prefix and (relative == prefix or relative.startswith(f"{prefix}/")):
            return True

    excluded_files: set[str] = set()
    for sqlite_path in (settings.db_path, settings.waline_db_path, settings.workflow_db_path):
        for candidate in (sqlite_path, *_sqlite_sidecar_paths(sqlite_path)):
            candidate_relative = _runtime_relative_prefix(settings, candidate)
            if candidate_relative:
                excluded_files.add(candidate_relative)
    return relative in excluded_files


def _iter_runtime_files(settings) -> list[tuple[Path, str]]:
    data_root = settings.data_dir.expanduser().resolve()
    if not data_root.exists():
        return []
    files: list[tuple[Path, str]] = []
    for item in sorted(data_root.rglob("*")):
        if item.is_symlink() or not item.is_file():
            continue
        try:
            relative = item.resolve().relative_to(data_root).as_posix()
        except ValueError:
            continue
        if _runtime_relative_is_excluded(settings, relative):
            continue
        files.append((item, relative))
    return files


def _tar_runtime_files(settings, dest_tar: Path) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest_tar, "w") as archive:
        for path, relative in _iter_runtime_files(settings):
            archive.add(path, arcname=relative)


def _restore_runtime_files_from_stage(staging_dir: Path, settings) -> None:
    data_root = settings.data_dir.expanduser().resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    staged_files: list[tuple[Path, str]] = []
    for item in sorted(staging_dir.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(staging_dir).as_posix()
        if _runtime_relative_is_excluded(settings, relative):
            raise ValidationError(f"Backup runtime_files contains excluded path: {relative}")
        staged_files.append((item, relative))

    current_dirs: set[Path] = set()
    for path, _relative in _iter_runtime_files(settings):
        current_dirs.add(path.parent)
        path.unlink(missing_ok=True)

    for source, relative in staged_files:
        target_path = (data_root / relative).resolve()
        if data_root != target_path and not str(target_path).startswith(f"{data_root}{os.sep}"):
            raise ValidationError("Refusing to restore runtime file outside data directory")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target_path)

    for directory in sorted(current_dirs, key=lambda item: len(item.parts), reverse=True):
        with suppress(OSError):
            directory.rmdir()


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
            "datasets/runtime-files.tar.zst": "runtime_files",
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


def _ensure_remote_repo_identity(config, credentials: BackupCredentialBundle, transport: BackupTransport) -> None:
    expected = _repo_identity_payload(config, credentials)
    if not hasattr(transport, "fetch_repo_identity") or not hasattr(transport, "write_repo_identity"):
        return
    current = transport.fetch_repo_identity()
    if current is None:
        transport.write_repo_identity(expected)
        return
    accepted_repo_ids = _accepted_runtime_repo_ids(
        site_slug=str(config.site_slug),
        credential_ref=str(config.credential_ref) if config.credential_ref else None,
    )
    accepted_repo_ids.add(expected["repo_id"])
    if current.get("repo_id") not in accepted_repo_ids:
        raise ValidationError("远端备份历史属于另一套 Serino。请先在后台选择从备份机历史恢复数据或覆盖远端历史。")


class SftpTransport:
    def __init__(self, *, host: str, port: int, username: str, remote_root: str, site_slug: str) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._remote_root = remote_root.rstrip("/")
        self._site_slug = site_slug

    def begin_session(self, *, timeout_seconds: int | None = None) -> dict[str, Any]:
        self._mkdirs(
            self._remote_root,
            self._site_root(),
            self._catalog_root(),
            self._commits_root(),
            self._datasets_root(),
            timeout_seconds=timeout_seconds,
        )
        return {"session_id": uuid_str(), "site_slug": self._site_slug}

    def probe_write_access(self, *, timeout_seconds: int | None = None) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write("backup-probe\n")
            tmp_path = Path(tmp.name)
        probe_remote = f"{self._catalog_root()}/probes/{uuid_str()}.txt"
        try:
            self._mkdirs(str(PurePosixPath(probe_remote).parent), timeout_seconds=timeout_seconds)
            self._run_batch(
                [f"put {tmp_path} {probe_remote}", f"rm {probe_remote}"],
                timeout=float(timeout_seconds) if timeout_seconds is not None else None,
                quick_connect=timeout_seconds is not None,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _sanitize_sftp_path(path: str) -> str:
        if _SFTP_UNSAFE_RE.search(path):
            raise ValidationError(f"SFTP path contains unsafe characters: {path!r}")
        return path

    def _run_batch(
        self,
        commands: list[str],
        *,
        check: bool = True,
        timeout: float | None = None,
        quick_connect: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        sanitized = [self._sanitize_sftp_path(cmd) for cmd in commands]
        payload = "\n".join(sanitized) + "\n"
        args = ["sftp"]
        if quick_connect:
            timeout_seconds = max(1, int(timeout or 3))
            args.extend(
                [
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={timeout_seconds}",
                    "-o",
                    "ConnectionAttempts=1",
                    "-o",
                    "ServerAliveInterval=2",
                    "-o",
                    "ServerAliveCountMax=1",
                ]
            )
        args.extend(["-P", str(self._port)])
        ssh_config = _backup_ssh_config_path()
        if ssh_config.exists():
            args.extend(["-F", str(ssh_config)])
        args.extend(["-b", "-", f"{self._username}@{self._host}"])
        run_kwargs: dict[str, Any] = {
            "input": payload,
            "text": True,
            "capture_output": True,
            "check": False,
        }
        if timeout is not None:
            run_kwargs["timeout"] = timeout + 1
        try:
            proc = subprocess.run(args, **run_kwargs)
        except subprocess.TimeoutExpired as exc:
            raise ValidationError("连接备份机超时，请执行临时接入命令。") from exc
        if check and proc.returncode != 0:
            raise ValidationError(proc.stderr.strip() or "SFTP command failed")
        return proc

    def _mkdirs(self, *paths: str, timeout_seconds: int | None = None) -> None:
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
                    commands.append(f"-mkdir {posix}")
        self._run_batch(
            commands,
            check=False,
            timeout=float(timeout_seconds) if timeout_seconds is not None else None,
            quick_connect=timeout_seconds is not None,
        )

    def _site_root(self) -> str:
        return f"{self._remote_root}/current"

    def _archive_root(self) -> str:
        return f"{self._remote_root}/archived"

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

    def _repo_identity_path(self) -> str:
        return f"{self._site_root()}/repo.json"

    def _recovery_keyring_path(self) -> str:
        return f"{self._catalog_root()}/recovery-keyring.json"

    def _human_commit_dir(self, commit_id: str, created_at: str) -> str:
        dt = datetime.fromisoformat(created_at)
        return f"{self._commits_root()}/{dt:%Y/%m/%d}/{dt:%Y%m%dT%H%M%SZ}-{commit_id}"

    def _commit_marker_path(self, commit_id: str, *, created_at: str, backup_path: str | None = None) -> str:
        if backup_path:
            marker_path = PurePosixPath(backup_path).as_posix()
            commits_root = PurePosixPath(self._commits_root()).as_posix()
            if marker_path.startswith(f"{commits_root}/") and marker_path.endswith("/manifest.json"):
                return marker_path
            logger.warning("Ignoring unexpected remote backup marker path for commit %s", commit_id)
        return f"{self._human_commit_dir(commit_id, created_at)}/manifest.json"

    def fetch_repo_identity(self) -> dict[str, Any] | None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "repo.json"
            proc = self._run_batch([f"get {self._repo_identity_path()} {local_path}"], check=False)
            if proc.returncode != 0 or not local_path.exists():
                return None
            try:
                return json.loads(local_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValidationError("远端备份仓库身份文件无法解析。") from exc

    def probe_repo_identity(
        self,
        *,
        timeout_seconds: int = 3,
    ) -> tuple[bool, dict[str, Any] | None, str | None]:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "repo.json"
            try:
                proc = self._run_batch(
                    [f"get {self._repo_identity_path()} {local_path}"],
                    check=False,
                    timeout=float(timeout_seconds),
                    quick_connect=True,
                )
            except ValidationError as exc:
                return False, None, str(exc)
            if proc.returncode == 0 and local_path.exists():
                try:
                    return True, json.loads(local_path.read_text(encoding="utf-8")), None
                except json.JSONDecodeError:
                    return False, None, "远端备份仓库身份文件无法解析。"

            output = f"{proc.stderr or ''}\n{proc.stdout or ''}".strip()
            if _remote_path_is_missing(output):
                return True, None, None
            return (
                False,
                None,
                output or "无法使用 serino-backup 快速连接备份机，需要执行临时接入命令。",
            )

    def write_repo_identity(self, payload: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            tmp_path = Path(tmp.name)
        try:
            self._mkdirs(self._site_root())
            self._run_batch([f"put {tmp_path} {self._repo_identity_path()}"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def fetch_recovery_keyring(self) -> dict[str, Any] | None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "recovery-keyring.json"
            proc = self._run_batch([f"get {self._recovery_keyring_path()} {local_path}"], check=False)
            if proc.returncode != 0:
                output = f"{proc.stderr or ''}\n{proc.stdout or ''}".strip()
                if _remote_path_is_missing(output):
                    return None
                detail = output or "SFTP command failed"
                raise ValidationError(f"无法使用 serino-backup 连接备份机，请先执行临时接入命令。{detail}")
            if not local_path.exists():
                return None
            try:
                return json.loads(local_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValidationError("远端恢复钥匙包无法解析。") from exc

    def write_recovery_keyring(self, payload: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            tmp_path = Path(tmp.name)
        try:
            self._mkdirs(self._catalog_root())
            self._run_batch([f"put {tmp_path} {self._recovery_keyring_path()}"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def archive_current_repo(self, *, remote_repo_id: str | None = None) -> str:
        safe_repo_id = re.sub(r"[^A-Za-z0-9._-]", "-", remote_repo_id or "unknown")[:48] or "unknown"
        archive_dir = f"{self._archive_root()}/{_utcnow():%Y%m%dT%H%M%S}-{safe_repo_id}"
        self._mkdirs(self._archive_root())
        self._run_batch([f"rename {self._site_root()} {archive_dir}"], check=False)
        self.begin_session()
        return archive_dir

    def _remove_remote_path(self, path: str, *, allow_missing: bool = True) -> bool:
        proc = self._run_batch([f"rm {path}"], check=False)
        if proc.returncode == 0:
            return True
        output = f"{proc.stderr or ''}\n{proc.stdout or ''}".strip()
        if allow_missing and _remote_path_is_missing(output):
            return False
        raise ValidationError(output or "SFTP command failed")

    def has_chunk(self, digest: str) -> bool:
        proc = self._run_batch([f"ls {self._chunk_path(digest)}"], check=False)
        return proc.returncode == 0

    def has_chunks(self, digests: list[str]) -> dict[str, bool]:
        """Check existence of multiple chunks in a single SFTP session."""
        if not digests:
            return {}
        commands = [f"-ls {self._chunk_path(d)}" for d in digests]
        proc = self._run_batch(commands, check=False)
        stdout_lines = [
            line.strip()
            for line in (proc.stdout or "").splitlines()
            if line.strip() and not line.lstrip().startswith("sftp>")
        ]
        result: dict[str, bool] = {}
        for d in digests:
            result[d] = any(d in line for line in stdout_lines)
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

    def delete_commit(self, commit_id: str, *, created_at: str, backup_path: str | None = None) -> None:
        """Remove a commit's index entry and human-readable directory from remote."""
        index_path = self._commit_index_path(commit_id)
        marker_path = self._commit_marker_path(commit_id, created_at=created_at, backup_path=backup_path)
        self._remove_remote_path(index_path)
        try:
            self._remove_remote_path(marker_path)
        except Exception:
            logger.warning("Failed to delete remote backup commit marker %s", commit_id, exc_info=True)

    def delete_manifest(self, digest: str) -> None:
        self._remove_remote_path(self._manifest_path(digest))

    def delete_manifests(self, digests: list[str]) -> None:
        if not digests:
            return
        for digest in digests:
            self.delete_manifest(digest)

    def delete_chunk(self, digest: str) -> None:
        self._remove_remote_path(self._chunk_path(digest))

    def delete_chunks(self, digests: list[str]) -> None:
        if not digests:
            return
        for digest in digests:
            self.delete_chunk(digest)

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

    def download_chunks(self, digests: list[str], destination_dir: Path) -> dict[str, Path]:
        if not digests:
            return {}
        destination_dir.mkdir(parents=True, exist_ok=True)
        unique_digests = list(dict.fromkeys(digests))
        commands = [f"get {self._chunk_path(digest)} {destination_dir / digest}" for digest in unique_digests]
        self._run_batch(commands)
        return {digest: destination_dir / digest for digest in unique_digests}


def restore_backup_commit(session: Session, commit_id: str) -> BackupCommitRead:
    commit = repo.get_backup_commit(session, commit_id)
    if commit is None:
        raise ResourceNotFound("Backup commit not found")
    commit_record = _backup_commit_restore_record(commit)
    all_records = repo.list_backup_commits(session, include_retention_tombstones=True)
    config = get_or_create_backup_sync_config(session)
    credentials = load_backup_credentials(config.credential_ref)
    transport = build_transport(config, credentials)
    commit_payload = transport.fetch_commit(commit.remote_commit_id)
    manifest = transport.fetch_manifest(commit_payload["manifest_digest"])
    response = _commit_read(commit)
    session.close()
    _restore_from_manifest(manifest, transport, credentials)
    restored_at = _utcnow()
    try:
        with get_session_factory()() as restored_session:
            _repair_restored_backup_runtime_state(restored_session, restored_at=restored_at)
            restored_commit = repo.get_backup_commit(restored_session, commit_id)
            if restored_commit is None:
                restored_commit = repo.create_backup_commit(restored_session, **commit_record)
            if restored_commit is not None:
                restored_commit.restored_at = restored_at
            restored_session.commit()
    except Exception:
        logger.warning("Failed to persist backup restored_at after runtime restore", exc_info=True)
    try:
        _prune_remote_commits_after_restore(transport, restored_commit_id=commit_id, all_records=all_records)
    except Exception:
        logger.warning("Failed to prune remote backup commits after restore", exc_info=True)
    return response.model_copy(update={"restored_at": restored_at})


def _backup_commit_restore_record(commit) -> dict[str, Any]:
    return {
        "id": commit.id,
        "transport": commit.transport,
        "trigger_kind": commit.trigger_kind,
        "site_slug": commit.site_slug,
        "remote_commit_id": commit.remote_commit_id,
        "manifest_digest": commit.manifest_digest,
        "backup_path": commit.backup_path,
        "datasets": copy.deepcopy(commit.datasets or {}),
        "stats_json": copy.deepcopy(commit.stats_json or {}),
        "snapshot_started_at": commit.snapshot_started_at,
        "snapshot_finished_at": commit.snapshot_finished_at,
        "restored_at": commit.restored_at,
        "created_at": commit.created_at,
        "updated_at": commit.updated_at,
    }


def restore_backup_snapshot(session: Session, snapshot_id: str) -> BackupSnapshotRead:
    commit = repo.get_backup_commit(session, snapshot_id)
    if commit is None:
        raise ResourceNotFound("Backup snapshot not found")
    restored = restore_backup_commit(session, snapshot_id)
    return _to_snapshot(restored)


def _restore_prune_plan(restored_commit_id: str, all_records: list[Any]) -> tuple[list[Any], list[Any]]:
    visible_records = [commit for commit in all_records if commit.trigger_kind != BACKUP_RETENTION_TOMBSTONE_TRIGGER]
    to_remove: list[Any] = []
    protected: list[Any] = []
    found_restored_commit = False
    for commit in visible_records:
        if str(commit.id) == restored_commit_id:
            found_restored_commit = True
            protected.append(commit)
            continue
        if found_restored_commit:
            protected.append(commit)
        else:
            to_remove.append(commit)
    if not found_restored_commit:
        return [], visible_records
    return to_remove, protected


def _prune_remote_commits_after_restore(
    transport: BackupTransport,
    *,
    restored_commit_id: str,
    all_records: list[Any],
) -> None:
    to_remove, protected = _restore_prune_plan(restored_commit_id, all_records)
    removed: list[Any] = []
    for commit in to_remove:
        if _delete_remote_commit_index(transport, commit):
            removed.append(commit)
        else:
            protected.append(commit)
    if not removed:
        return
    _cleanup_unreferenced_remote_objects(
        transport,
        cleanup_candidates=removed,
        protected_commits=protected,
    )


def _repair_restored_backup_runtime_state(session: Session, *, restored_at: datetime) -> None:
    message = "Backup run was interrupted by a runtime restore"
    for run in repo.list_sync_runs(session):
        if run.job_name == BACKUP_JOB_NAME and run.status == "running":
            run.status = "failed"
            run.finished_at = restored_at
            run.last_error = message
            run.message = message
    for item in repo.list_backup_queue_items(session):
        if item.status in {"queued", "running", "retrying"}:
            item.status = "failed"
            item.finished_at = restored_at
            item.next_retry_at = None
            item.last_error = message


def _restore_from_manifest(
    manifest: dict[str, Any],
    transport: BackupTransport,
    credentials: BackupCredentialBundle,
) -> None:
    settings = get_settings()
    temp_dir = settings.backup_sync_tmp_dir / f"restore-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    staging_media: Path | None = None
    staging_secrets: Path | None = None
    staging_packs: Path | None = None
    staging_runtime_files: Path | None = None
    media_swapped = False
    secrets_swapped = False
    packs_swapped = False

    with _restore_lock:
        _restore_in_progress.set()
    try:
        datasets = manifest["datasets"]
        chunk_cache = _prefetch_manifest_chunks(temp_dir, manifest, transport)

        aerisun_zst = _materialize_manifest_payload(
            temp_dir, datasets["aerisun_db"], transport, credentials, chunk_cache=chunk_cache
        )
        waline_zst = _materialize_manifest_payload(
            temp_dir, datasets["waline_db"], transport, credentials, chunk_cache=chunk_cache
        )
        workflow_entry = datasets.get("workflow_db")
        workflow_zst = (
            _materialize_manifest_payload(temp_dir, workflow_entry, transport, credentials, chunk_cache=chunk_cache)
            if workflow_entry
            else None
        )
        secrets_zst = _materialize_manifest_payload(
            temp_dir, datasets["secrets"], transport, credentials, chunk_cache=chunk_cache
        )
        automation_packs_entry = datasets.get("automation_packs")
        automation_packs_zst = (
            _materialize_manifest_payload(
                temp_dir, automation_packs_entry, transport, credentials, chunk_cache=chunk_cache
            )
            if automation_packs_entry
            else None
        )
        runtime_files_entry = datasets.get("runtime_files")
        runtime_files_zst = (
            _materialize_manifest_payload(
                temp_dir, runtime_files_entry, transport, credentials, chunk_cache=chunk_cache
            )
            if runtime_files_entry
            else None
        )

        aerisun_restore = temp_dir / "aerisun.restore.sqlite"
        waline_restore = temp_dir / "waline.restore.sqlite"
        workflow_restore = temp_dir / "workflow.restore.sqlite"
        secrets_tar = temp_dir / "secrets.tar"
        automation_packs_tar = temp_dir / "automation-packs.tar"
        runtime_files_tar = temp_dir / "runtime-files.tar"

        _zstd_decompress_file(aerisun_zst, aerisun_restore)
        _zstd_decompress_file(waline_zst, waline_restore)
        if workflow_zst is not None:
            _zstd_decompress_file(workflow_zst, workflow_restore)
        _zstd_decompress_file(secrets_zst, secrets_tar)
        if automation_packs_zst is not None:
            _zstd_decompress_file(automation_packs_zst, automation_packs_tar)
        if runtime_files_zst is not None:
            _zstd_decompress_file(runtime_files_zst, runtime_files_tar)

        # Materialize and verify every non-database payload before swapping runtime data.
        staging_media = settings.media_dir.parent / f".media-staging-{uuid.uuid4().hex}"
        staging_media.mkdir(parents=True, exist_ok=True)
        for file_entry in datasets["media"]["files"]:
            target_path = (staging_media / file_entry["path"].removeprefix("media/")).resolve()
            if not str(target_path).startswith(str(staging_media.resolve())):
                raise ValidationError("Refusing to restore media file outside media directory")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            source_path = _materialize_manifest_payload(
                temp_dir, file_entry, transport, credentials, chunk_cache=chunk_cache
            )
            shutil.copy2(source_path, target_path)

        staging_secrets = settings.secrets_dir.parent / f".secrets-staging-{uuid.uuid4().hex}"
        staging_secrets.mkdir(parents=True, exist_ok=True)
        _restore_secrets_tar(secrets_tar, staging_secrets)
        if settings.secrets_dir.exists():
            backup_sync_dir = settings.secrets_dir / "backup-sync"
            if backup_sync_dir.exists():
                shutil.copytree(backup_sync_dir, staging_secrets / "backup-sync", dirs_exist_ok=True)

        if automation_packs_zst is not None:
            automation_packs_root = settings.data_dir / "automation" / "packs"
            staging_packs = automation_packs_root.parent / f".packs-staging-{uuid.uuid4().hex}"
            staging_packs.mkdir(parents=True, exist_ok=True)
            _restore_tar_directory(automation_packs_tar, staging_packs)

        if runtime_files_zst is not None:
            staging_runtime_files = temp_dir / "runtime-files-staging"
            staging_runtime_files.mkdir(parents=True, exist_ok=True)
            _restore_tar_directory(runtime_files_tar, staging_runtime_files)

        # --- Atomic swap: databases via temp file + os.replace ---
        dispose_engine()
        _atomic_sqlite_replace(aerisun_restore, settings.db_path)
        _atomic_sqlite_replace(waline_restore, settings.waline_db_path)
        if workflow_zst is not None:
            _atomic_sqlite_replace(workflow_restore, settings.workflow_db_path)

        # --- Media: swap the already verified staging tree ---
        old_media = settings.media_dir.parent / f".media-old-{uuid.uuid4().hex}"
        if settings.media_dir.exists():
            os.rename(settings.media_dir, old_media)
        os.rename(staging_media, settings.media_dir)
        media_swapped = True
        if old_media.exists():
            shutil.rmtree(old_media, ignore_errors=True)

        # --- Secrets: swap the already verified staging tree ---
        old_secrets = settings.secrets_dir.parent / f".secrets-old-{uuid.uuid4().hex}"
        if settings.secrets_dir.exists():
            os.rename(settings.secrets_dir, old_secrets)
        os.rename(staging_secrets, settings.secrets_dir)
        secrets_swapped = True
        if old_secrets.exists():
            shutil.rmtree(old_secrets, ignore_errors=True)

        # --- Automation packs: swap the already verified staging tree ---
        if staging_packs is not None:
            automation_packs_root = settings.data_dir / "automation" / "packs"
            old_packs = automation_packs_root.parent / f".packs-old-{uuid.uuid4().hex}"
            if automation_packs_root.exists():
                os.rename(automation_packs_root, old_packs)
            os.rename(staging_packs, automation_packs_root)
            packs_swapped = True
            if old_packs.exists():
                shutil.rmtree(old_packs, ignore_errors=True)

        # --- Misc runtime files: synchronize the snapshot for non-specialized store files. ---
        if staging_runtime_files is not None:
            _restore_runtime_files_from_stage(staging_runtime_files, settings)
    finally:
        _restore_in_progress.clear()
        if staging_media is not None and not media_swapped and staging_media.exists():
            shutil.rmtree(staging_media, ignore_errors=True)
        if staging_secrets is not None and not secrets_swapped and staging_secrets.exists():
            shutil.rmtree(staging_secrets, ignore_errors=True)
        if staging_packs is not None and not packs_swapped and staging_packs.exists():
            shutil.rmtree(staging_packs, ignore_errors=True)
        if staging_runtime_files is not None and staging_runtime_files.exists():
            shutil.rmtree(staging_runtime_files, ignore_errors=True)
        shutil.rmtree(temp_dir, ignore_errors=True)


def _manifest_chunk_digests(manifest: dict[str, Any]) -> list[str]:
    digests: list[str] = []
    seen: set[str] = set()

    def add_entry(entry: dict[str, Any]) -> None:
        for chunk in entry.get("chunks", []):
            digest = str(chunk["digest"])
            if digest not in seen:
                seen.add(digest)
                digests.append(digest)

    for dataset_key, entry in manifest["datasets"].items():
        if dataset_key == "media":
            for file_entry in entry.get("files", []):
                add_entry(file_entry)
        elif isinstance(entry, dict):
            add_entry(entry)
    return digests


def _prefetch_manifest_chunks(
    temp_dir: Path,
    manifest: dict[str, Any],
    transport: BackupTransport,
) -> dict[str, Path]:
    if not hasattr(transport, "download_chunks"):
        return {}
    digests = _manifest_chunk_digests(manifest)
    return transport.download_chunks(digests, temp_dir / "chunk-cache")


def _materialize_manifest_file(
    temp_dir: Path,
    entry: dict[str, Any],
    transport: BackupTransport,
    *,
    chunk_cache: dict[str, Path] | None = None,
) -> Path:
    local_path = temp_dir / Path(entry["path"]).name
    _write_chunks_to_path(entry["chunks"], local_path, transport, chunk_cache=chunk_cache)
    if _sha256_file(local_path) != entry["digest"]:
        raise ValidationError(f"Checksum mismatch while restoring {entry['path']}")
    return local_path


def _materialize_manifest_payload(
    temp_dir: Path,
    entry: dict[str, Any],
    transport: BackupTransport,
    credentials: BackupCredentialBundle,
    *,
    chunk_cache: dict[str, Path] | None = None,
) -> Path:
    payload_path = _materialize_manifest_file(temp_dir, entry, transport, chunk_cache=chunk_cache)
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


def _write_chunks_to_path(
    chunks: list[dict[str, Any]],
    destination: Path,
    transport: BackupTransport,
    *,
    chunk_cache: dict[str, Path] | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as fh:
        for chunk in chunks:
            digest = chunk["digest"]
            cached_path = chunk_cache.get(digest) if chunk_cache else None
            payload = cached_path.read_bytes() if cached_path is not None else transport.read_chunk(digest)
            if _sha256_bytes(payload) != chunk["digest"]:
                raise ValidationError("Downloaded backup chunk digest mismatch")
            fh.write(payload)
