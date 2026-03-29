from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519


class FakeBackupTransport:
    def __init__(self) -> None:
        self.chunks: dict[str, bytes] = {}
        self.manifests: dict[str, dict] = {}
        self.commits: dict[str, dict] = {}

    def begin_session(self) -> dict[str, str]:
        return {"session_id": "fake-session", "site_slug": "test-site"}

    def has_chunk(self, digest: str) -> bool:
        return digest in self.chunks

    def upload_chunk(self, digest: str, chunk_path: Path) -> None:
        self.chunks[digest] = chunk_path.read_bytes()

    def upload_manifest(self, digest: str, payload: bytes) -> None:
        self.manifests[digest] = json.loads(payload.decode("utf-8"))

    def commit(self, *, commit_id: str, manifest_digest: str, manifest: dict) -> dict[str, str]:
        payload = {
            "commit_id": commit_id,
            "site_slug": manifest["site_slug"],
            "remote_commit_id": commit_id,
            "manifest_digest": manifest_digest,
            "backup_path": f"/sites/{manifest['site_slug']}/commits/{commit_id}/manifest.json",
            "created_at": manifest["created_at"],
        }
        self.commits[commit_id] = payload
        return {"remote_commit_id": commit_id, "backup_path": payload["backup_path"]}

    def list_commits(self) -> list[dict]:
        return list(self.commits.values())

    def fetch_commit(self, commit_id: str) -> dict:
        return self.commits[commit_id]

    def fetch_manifest(self, digest: str) -> dict:
        return self.manifests[digest]

    def read_chunk(self, digest: str) -> bytes:
        return self.chunks[digest]


def _write_backup_credentials(secrets_dir: Path, credential_ref: str) -> None:
    key_dir = secrets_dir / "backup-sync" / credential_ref
    key_dir.mkdir(parents=True, exist_ok=True)

    signing_private = ed25519.Ed25519PrivateKey.generate()
    signing_public = signing_private.public_key()
    secrets_private = x25519.X25519PrivateKey.generate()
    secrets_public = secrets_private.public_key()

    key_dir.joinpath("client_ed25519.pem").write_bytes(
        signing_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_dir.joinpath("client_ed25519.pub.pem").write_bytes(
        signing_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    key_dir.joinpath("secrets_x25519.pem").write_bytes(
        secrets_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_dir.joinpath("secrets_x25519.pub.pem").write_bytes(
        secrets_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def test_backup_sync_endpoints_create_run_commit_and_restore(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    from aerisun.core.settings import get_settings

    app_settings = get_settings()
    _write_backup_credentials(app_settings.secrets_dir, "default")
    app_settings.media_dir.mkdir(parents=True, exist_ok=True)
    app_settings.media_dir.joinpath("nested").mkdir(parents=True, exist_ok=True)
    app_settings.media_dir.joinpath("nested/hello.txt").write_text("hello backup", encoding="utf-8")
    app_settings.secrets_dir.joinpath("app-secret.txt").write_text("super-secret", encoding="utf-8")

    update_response = client.put(
        "/api/v1/admin/system/backup-sync/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "paused": False,
            "interval_minutes": 60,
            "transport_mode": "receiver",
            "site_slug": "test-site",
            "receiver_base_url": "http://backup-receiver.invalid",
            "credential_ref": "default",
            "age_public_key_fingerprint": "pending",
            "max_retries": 2,
            "retry_backoff_seconds": 60,
        },
    )
    assert update_response.status_code == 200

    run_response = client.post("/api/v1/admin/system/backup-sync/runs", headers=admin_headers)
    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    assert run_payload["commit_id"]

    queue_response = client.get("/api/v1/admin/system/backup-sync/queue", headers=admin_headers)
    assert queue_response.status_code == 200
    assert queue_response.json()[0]["status"] == "completed"

    commits_response = client.get("/api/v1/admin/system/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    commits = commits_response.json()
    assert len(commits) == 1
    commit_id = commits[0]["id"]
    assert commits[0]["datasets"]["media"]["files"]

    backups_response = client.get("/api/v1/admin/system/backups", headers=admin_headers)
    assert backups_response.status_code == 200
    assert backups_response.json()[0]["id"] == commit_id

    app_settings.media_dir.joinpath("nested/hello.txt").unlink()
    app_settings.db_path.unlink(missing_ok=True)
    app_settings.waline_db_path.unlink(missing_ok=True)

    restore_response = client.post(
        f"/api/v1/admin/system/backup-sync/commits/{commit_id}/restore", headers=admin_headers
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["restored_at"] is not None
    assert app_settings.media_dir.joinpath("nested/hello.txt").read_text(encoding="utf-8") == "hello backup"
    assert app_settings.secrets_dir.joinpath("app-secret.txt").read_text(encoding="utf-8") == "super-secret"


def test_pause_and_resume_backup_sync(client, admin_headers) -> None:
    pause_response = client.post("/api/v1/admin/system/backup-sync/pause", headers=admin_headers)
    assert pause_response.status_code == 200
    assert pause_response.json()["paused"] is True

    resume_response = client.post("/api/v1/admin/system/backup-sync/resume", headers=admin_headers)
    assert resume_response.status_code == 200
    assert resume_response.json()["paused"] is False
