from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from aerisun.core.settings import get_settings


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

    secrets_private = x25519.X25519PrivateKey.generate()
    secrets_public = secrets_private.public_key()

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
    with sqlite3.connect(app_settings.workflow_db_path) as connection:
        connection.execute("create table if not exists backup_probe (id integer primary key, note text)")
        connection.execute("delete from backup_probe")
        connection.execute("insert into backup_probe (note) values (?)", ("workflow-backup",))
        connection.commit()

    export_response = client.post(
        "/api/v1/admin/system/backup-sync/recovery-key/export",
        headers=admin_headers,
        json={
            "credential_ref": "default",
            "site_slug": "test-site",
            "passphrase": "correct horse battery staple",
            "rotate": False,
        },
    )
    assert export_response.status_code == 200
    acknowledge_response = client.post(
        "/api/v1/admin/system/backup-sync/recovery-key/acknowledge",
        headers=admin_headers,
        json={"credential_ref": "default"},
    )
    assert acknowledge_response.status_code == 200

    update_response = client.put(
        "/api/v1/admin/system/backup-sync/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "paused": False,
            "interval_minutes": 60,
            "transport_mode": "sftp",
            "site_slug": "test-site",
            "remote_host": "backup.example.com",
            "remote_port": 22,
            "remote_path": "/srv/aerisun/backup",
            "remote_username": "backup-user",
            "credential_ref": "default",
            "encrypt_runtime_data": True,
            "max_retries": 2,
            "retry_backoff_seconds": 60,
        },
    )
    assert update_response.status_code == 200

    pack_dir = app_settings.data_dir / "automation" / "packs" / "community_moderation_v1"
    pack_dir.mkdir(parents=True, exist_ok=True)
    marker_path = pack_dir / "backup-marker.txt"
    marker_path.write_text("pack-backup", encoding="utf-8")

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
    assert commits[0]["datasets"]["aerisun_db"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commits[0]["datasets"]["media"]["files"][0]["encryption"]["scheme"] == "x25519-aesgcm"

    backups_response = client.get("/api/v1/admin/system/backups", headers=admin_headers)
    assert backups_response.status_code == 200
    assert backups_response.json()[0]["id"] == commit_id

    app_settings.media_dir.joinpath("nested/hello.txt").unlink()
    app_settings.db_path.unlink(missing_ok=True)
    app_settings.waline_db_path.unlink(missing_ok=True)
    app_settings.workflow_db_path.unlink(missing_ok=True)
    marker_path.unlink()

    restore_response = client.post(
        f"/api/v1/admin/system/backup-sync/commits/{commit_id}/restore", headers=admin_headers
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["restored_at"] is not None
    assert app_settings.media_dir.joinpath("nested/hello.txt").read_text(encoding="utf-8") == "hello backup"
    assert app_settings.secrets_dir.joinpath("app-secret.txt").read_text(encoding="utf-8") == "super-secret"
    with sqlite3.connect(app_settings.workflow_db_path) as connection:
        restored = connection.execute("select note from backup_probe order by id asc").fetchone()
    assert restored is not None
    assert restored[0] == "workflow-backup"
    assert marker_path.read_text(encoding="utf-8") == "pack-backup"


def test_backup_sync_config_test_endpoint_reports_connectivity(client, admin_headers, monkeypatch) -> None:
    monkeypatch.setattr(
        "aerisun.domain.ops.backup_sync.SftpTransport.begin_session",
        lambda self: {"session_id": "s", "site_slug": "test-site"},
    )
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.SftpTransport.probe_write_access", lambda self: None)

    response = client.post(
        "/api/v1/admin/system/backup-sync/config/test",
        headers=admin_headers,
        json={
            "enabled": True,
            "paused": False,
            "interval_minutes": 60,
            "transport_mode": "sftp",
            "site_slug": "test-site",
            "remote_host": "backup.example.com",
            "remote_port": 222,
            "remote_path": "/srv/aerisun/backup",
            "remote_username": "backup-user",
            "credential_ref": "default",
            "encrypt_runtime_data": False,
            "max_retries": 2,
            "retry_backoff_seconds": 60,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["remote_path_preview"] == "/srv/aerisun/backup/sites/test-site"
    assert payload["recovery_key_ready"] is False
    assert payload["recovery_key_acknowledged"] is False


def test_ensure_backup_credentials_endpoint_creates_and_reuses_keys(client, admin_headers) -> None:
    first = client.post(
        "/api/v1/admin/system/backup-sync/credentials/ensure",
        headers=admin_headers,
        json={"credential_ref": "auto-demo", "site_slug": "test-site"},
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["created"] is True
    assert first_payload["credential_ref"] == "auto-demo"
    assert first_payload["site_slug"] == "test-site"
    assert first_payload["credential_dir"].endswith("/backup-sync/auto-demo")
    assert first_payload["secrets_fingerprint"]

    second = client.post(
        "/api/v1/admin/system/backup-sync/credentials/ensure",
        headers=admin_headers,
        json={"credential_ref": "auto-demo", "site_slug": "test-site"},
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["secrets_fingerprint"] == first_payload["secrets_fingerprint"]


def test_backup_sync_config_requires_recovery_key_export_first(client, admin_headers) -> None:
    _write_backup_credentials(get_settings().secrets_dir, "default")
    response = client.put(
        "/api/v1/admin/system/backup-sync/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "paused": False,
            "interval_minutes": 60,
            "transport_mode": "sftp",
            "site_slug": "test-site",
            "remote_host": "backup.example.com",
            "remote_port": 22,
            "remote_path": "/srv/aerisun/backup",
            "remote_username": "backup-user",
            "credential_ref": "default",
            "encrypt_runtime_data": False,
            "max_retries": 2,
            "retry_backoff_seconds": 60,
        },
    )
    assert response.status_code == 422
    assert "恢复私钥" in response.json()["detail"]


def test_backup_sync_config_requires_recovery_key_acknowledgement(client, admin_headers) -> None:
    _write_backup_credentials(get_settings().secrets_dir, "default")
    export_response = client.post(
        "/api/v1/admin/system/backup-sync/recovery-key/export",
        headers=admin_headers,
        json={
            "credential_ref": "default",
            "site_slug": "test-site",
            "passphrase": "correct horse battery staple",
            "rotate": False,
        },
    )
    assert export_response.status_code == 200

    response = client.put(
        "/api/v1/admin/system/backup-sync/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "paused": False,
            "interval_minutes": 60,
            "transport_mode": "sftp",
            "site_slug": "test-site",
            "remote_host": "backup.example.com",
            "remote_port": 22,
            "remote_path": "/srv/aerisun/backup",
            "remote_username": "backup-user",
            "credential_ref": "default",
            "encrypt_runtime_data": False,
            "max_retries": 2,
            "retry_backoff_seconds": 60,
        },
    )
    assert response.status_code == 422
    assert "复制或下载" in response.json()["detail"]


def test_export_and_rotate_recovery_key(client, admin_headers) -> None:
    export_response = client.post(
        "/api/v1/admin/system/backup-sync/recovery-key/export",
        headers=admin_headers,
        json={
            "credential_ref": "vault-demo",
            "site_slug": "test-site",
            "passphrase": "correct horse battery staple",
            "rotate": False,
        },
    )
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["private_key_pem"].startswith("-----BEGIN PRIVATE KEY-----")
    assert export_payload["rotated"] is False
    first_fingerprint = export_payload["secrets_fingerprint"]

    rotate_response = client.post(
        "/api/v1/admin/system/backup-sync/recovery-key/export",
        headers=admin_headers,
        json={
            "credential_ref": "vault-demo",
            "site_slug": "test-site",
            "passphrase": "correct horse battery staple",
            "rotate": True,
        },
    )
    assert rotate_response.status_code == 200
    rotate_payload = rotate_response.json()
    assert rotate_payload["rotated"] is True
    assert rotate_payload["secrets_fingerprint"] != first_fingerprint
    assert first_fingerprint in rotate_payload["archived_fingerprints"]

    acknowledge_response = client.post(
        "/api/v1/admin/system/backup-sync/recovery-key/acknowledge",
        headers=admin_headers,
        json={"credential_ref": "vault-demo"},
    )
    assert acknowledge_response.status_code == 200


def test_pause_and_resume_backup_sync(client, admin_headers) -> None:
    pause_response = client.post("/api/v1/admin/system/backup-sync/pause", headers=admin_headers)
    assert pause_response.status_code == 200
    assert pause_response.json()["paused"] is True

    resume_response = client.post("/api/v1/admin/system/backup-sync/resume", headers=admin_headers)
    assert resume_response.status_code == 200
    assert resume_response.json()["paused"] is False
