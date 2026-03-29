from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

HEX64_RE = re.compile(r"^[a-f0-9]{64}$")
UUID_RE = re.compile(r"^[a-f0-9-]{36}$")


class ReceiverSessionRead(BaseModel):
    session_id: str
    site_slug: str
    upload_prefix: str
    created_at: float


class SessionCreateRequest(BaseModel):
    site_slug: str


class CommitCreateRequest(BaseModel):
    commit_id: str
    manifest_digest: str
    manifest: dict[str, Any]


@dataclass(slots=True)
class BackupReceiverSettings:
    data_dir: Path
    allowed_public_keys: dict[str, dict[str, str]] = field(default_factory=dict)
    max_timestamp_skew_seconds: int = 300
    enforce_local_only: bool = False


def load_settings_from_env() -> BackupReceiverSettings:
    data_dir = Path(os.environ.get("AERISUN_BACKUP_RECEIVER_DATA_DIR", ".store/backup-receiver"))
    allowlist_path = os.environ.get("AERISUN_BACKUP_RECEIVER_KEYS_FILE")
    raw_mapping = os.environ.get("AERISUN_BACKUP_RECEIVER_ALLOWED_KEYS_JSON")

    allowed_public_keys: dict[str, dict[str, str]] = {}
    if allowlist_path:
        allowed_public_keys = json.loads(Path(allowlist_path).read_text(encoding="utf-8"))
    elif raw_mapping:
        allowed_public_keys = json.loads(raw_mapping)

    return BackupReceiverSettings(
        data_dir=data_dir,
        allowed_public_keys=allowed_public_keys,
        enforce_local_only=os.environ.get("AERISUN_BACKUP_RECEIVER_ENFORCE_LOCAL_ONLY", "true").lower() != "false",
        max_timestamp_skew_seconds=int(os.environ.get("AERISUN_BACKUP_RECEIVER_MAX_SKEW_SECONDS", "300")),
    )


class ReceiverStorage:
    def __init__(self, settings: BackupReceiverSettings) -> None:
        self._settings = settings
        self._settings.data_dir.mkdir(parents=True, exist_ok=True)

    def site_root(self, site_slug: str) -> Path:
        return self._settings.data_dir / "sites" / site_slug

    def chunk_path(self, site_slug: str, digest: str) -> Path:
        return self.site_root(site_slug) / "catalog" / "chunks" / digest[:2] / digest[2:4] / digest

    def manifest_path(self, site_slug: str, digest: str) -> Path:
        return self.site_root(site_slug) / "catalog" / "manifests" / f"{digest}.json"

    def commit_index_path(self, site_slug: str, commit_id: str) -> Path:
        return self.site_root(site_slug) / "catalog" / "commit-index" / f"{commit_id}.json"

    def commit_dir(self, site_slug: str, commit_id: str, created_at: str) -> Path:
        from datetime import datetime

        dt = datetime.fromisoformat(created_at)
        return self.site_root(site_slug) / "commits" / f"{dt:%Y}" / f"{dt:%m}" / f"{dt:%d}" / f"{dt:%Y%m%dT%H%M%SZ}-{commit_id}"

    def ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def write_if_missing(self, path: Path, payload: bytes) -> None:
        if path.exists():
            return
        self.ensure_parent(path)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(path)

    def create_session(self, site_slug: str) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        session_path = self.site_root(site_slug) / "catalog" / "sessions" / f"{session_id}.json"
        self.ensure_parent(session_path)
        payload = {
            "session_id": session_id,
            "site_slug": site_slug,
            "upload_prefix": f"/sites/{site_slug}",
            "created_at": time.time(),
        }
        session_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload

    def session_exists(self, site_slug: str, session_id: str) -> bool:
        return (self.site_root(site_slug) / "catalog" / "sessions" / f"{session_id}.json").exists()

    def list_commits(self, site_slug: str) -> list[dict[str, Any]]:
        commit_dir = self.site_root(site_slug) / "catalog" / "commit-index"
        if not commit_dir.exists():
            return []
        items = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(commit_dir.glob("*.json"))]
        return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


def create_app(settings: BackupReceiverSettings) -> FastAPI:
    storage = ReceiverStorage(settings)
    app = FastAPI(title="Aerisun Backup Receiver", version="0.1.0")

    def _resolve_public_key(site_slug: str, key_fingerprint: str) -> ed25519.Ed25519PublicKey:
        site_keys = settings.allowed_public_keys.get(site_slug, {})
        pem = site_keys.get(key_fingerprint)
        if pem is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown backup signing key")
        public_key = serialization.load_pem_public_key(pem.encode("utf-8"))
        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid backup signing key type")
        return public_key

    async def _require_auth(
        request: Request,
        x_backup_site: str = Header(...),
        x_backup_key: str = Header(...),
        x_backup_timestamp: str = Header(...),
        x_backup_signature: str = Header(...),
        x_backup_session: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if settings.enforce_local_only:
            client_host = request.client.host if request.client else None
            if client_host not in {"127.0.0.1", "::1", "testclient"}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receiver only accepts loopback traffic")

        try:
            timestamp = int(x_backup_timestamp)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid backup timestamp") from exc
        now = int(time.time())
        if abs(now - timestamp) > settings.max_timestamp_skew_seconds:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Backup timestamp is outside allowed skew")

        body = await request.body()
        body_digest = __import__("hashlib").sha256(body).hexdigest()
        message = "\n".join([request.method.upper(), request.url.path, x_backup_site, x_backup_timestamp, body_digest]).encode("utf-8")
        public_key = _resolve_public_key(x_backup_site, x_backup_key)
        try:
            public_key.verify(base64.b64decode(x_backup_signature), message)
        except Exception as exc:  # pragma: no cover - cryptography raises several subclasses
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid backup signature") from exc

        if request.url.path != "/v1/sessions":
            if not x_backup_session or not storage.session_exists(x_backup_site, x_backup_session):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown backup session")

        return {"site_slug": x_backup_site, "session_id": x_backup_session}

    def _validate_digest(digest: str) -> None:
        if not HEX64_RE.fullmatch(digest):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Digest must be a sha256 hex string")

    def _validate_commit_id(commit_id: str) -> None:
        if not UUID_RE.fullmatch(commit_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Commit id must be a UUID string")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/sessions", response_model=ReceiverSessionRead)
    async def create_session(
        payload: SessionCreateRequest,
        auth: dict[str, Any] = Depends(_require_auth),
    ) -> ReceiverSessionRead:
        if payload.site_slug != auth["site_slug"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Site slug mismatch")
        return ReceiverSessionRead.model_validate(storage.create_session(payload.site_slug))

    @app.get("/v1/chunks/{digest}")
    async def chunk_exists(digest: str, auth: dict[str, Any] = Depends(_require_auth)) -> dict[str, bool]:
        _validate_digest(digest)
        return {"exists": storage.chunk_path(auth["site_slug"], digest).exists()}

    @app.put("/v1/chunks/{digest}", status_code=status.HTTP_204_NO_CONTENT)
    async def upload_chunk(digest: str, request: Request, auth: dict[str, Any] = Depends(_require_auth)) -> Response:
        _validate_digest(digest)
        payload = await request.body()
        actual = __import__("hashlib").sha256(payload).hexdigest()
        if actual != digest:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chunk digest mismatch")
        storage.write_if_missing(storage.chunk_path(auth["site_slug"], digest), payload)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/v1/chunks/{digest}/download")
    async def download_chunk(digest: str, auth: dict[str, Any] = Depends(_require_auth)) -> Response:
        _validate_digest(digest)
        path = storage.chunk_path(auth["site_slug"], digest)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")
        return Response(content=path.read_bytes(), media_type="application/octet-stream")

    @app.put("/v1/manifests/{digest}", status_code=status.HTTP_204_NO_CONTENT)
    async def upload_manifest(digest: str, request: Request, auth: dict[str, Any] = Depends(_require_auth)) -> Response:
        _validate_digest(digest)
        payload = await request.body()
        actual = __import__("hashlib").sha256(payload).hexdigest()
        if actual != digest:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manifest digest mismatch")
        json.loads(payload.decode("utf-8"))
        storage.write_if_missing(storage.manifest_path(auth["site_slug"], digest), payload)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/v1/manifests/{digest}")
    async def get_manifest(digest: str, auth: dict[str, Any] = Depends(_require_auth)) -> dict[str, Any]:
        _validate_digest(digest)
        path = storage.manifest_path(auth["site_slug"], digest)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manifest not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/v1/commits")
    async def create_commit(payload: CommitCreateRequest, auth: dict[str, Any] = Depends(_require_auth)) -> dict[str, Any]:
        _validate_commit_id(payload.commit_id)
        _validate_digest(payload.manifest_digest)
        manifest_path = storage.manifest_path(auth["site_slug"], payload.manifest_digest)
        if not manifest_path.exists():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manifest must be uploaded before commit")

        manifest = payload.manifest
        created_at = manifest.get("created_at")
        if not isinstance(created_at, str):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Manifest created_at is required")

        missing_chunks: list[str] = []
        for dataset_key, dataset in manifest.get("datasets", {}).items():
            if dataset_key == "media":
                files = dataset.get("files", [])
            else:
                files = [dataset]
            for file_entry in files:
                for chunk in file_entry.get("chunks", []):
                    digest = chunk.get("digest")
                    if not isinstance(digest, str) or not storage.chunk_path(auth["site_slug"], digest).exists():
                        missing_chunks.append(str(digest))
        if missing_chunks:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Missing chunks for commit: {','.join(missing_chunks[:5])}")

        commit_dir = storage.commit_dir(auth["site_slug"], payload.commit_id, created_at)
        commit_path = commit_dir / "manifest.json"
        backup_path = PurePosixPath("/sites") / auth["site_slug"] / commit_dir.relative_to(storage.site_root(auth["site_slug"])).as_posix() / "manifest.json"
        storage.write_if_missing(commit_path, manifest_path.read_bytes())

        index_payload = {
            "commit_id": payload.commit_id,
            "site_slug": auth["site_slug"],
            "remote_commit_id": payload.commit_id,
            "manifest_digest": payload.manifest_digest,
            "backup_path": backup_path.as_posix(),
            "created_at": created_at,
        }
        storage.write_if_missing(
            storage.commit_index_path(auth["site_slug"], payload.commit_id),
            json.dumps(index_payload, ensure_ascii=False).encode("utf-8"),
        )
        return index_payload

    @app.get("/v1/commits")
    async def list_commits(auth: dict[str, Any] = Depends(_require_auth)) -> dict[str, Any]:
        return {"items": storage.list_commits(auth["site_slug"])}

    @app.get("/v1/commits/{commit_id}")
    async def get_commit(commit_id: str, auth: dict[str, Any] = Depends(_require_auth)) -> dict[str, Any]:
        _validate_commit_id(commit_id)
        path = storage.commit_index_path(auth["site_slug"], commit_id)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commit not found")
        return json.loads(path.read_text(encoding="utf-8"))

    return app
