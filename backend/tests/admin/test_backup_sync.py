from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from aerisun.core.settings import get_settings

BASE = "/api/v1/admin/system"
RECOVERY_PASSPHRASE = "correct horse battery staple"
RESTORE_SPEED_LIMIT_SECONDS = 5.0


class FakeBackupTransport:
    def __init__(self) -> None:
        self.chunks: dict[str, bytes] = {}
        self.manifests: dict[str, dict] = {}
        self.commits: dict[str, dict] = {}
        self.downloaded_chunk_batches: list[list[str]] = []

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

    def download_chunks(self, digests: list[str], destination_dir: Path) -> dict[str, Path]:
        self.downloaded_chunk_batches.append(list(digests))
        destination_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        for digest in digests:
            path = destination_dir / digest
            path.write_bytes(self.chunks[digest])
            paths[digest] = path
        return paths


def test_sftp_mkdirs_keep_batch_running_when_parent_exists(monkeypatch) -> None:
    from aerisun.domain.ops.backup_sync import SftpTransport

    batches: list[str] = []

    def fake_run(args, *, input, text, capture_output, check):
        batches.append(input)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = SftpTransport(
        host="backup.example.test",
        port=22,
        username="ubuntu",
        remote_root="/home/ubuntu/aerisun-backup-test/site",
        site_slug="site",
    )
    transport._mkdirs("/home/ubuntu/aerisun-backup-test/site/catalog/probes")

    assert batches
    assert batches[-1].splitlines() == [
        "-mkdir /home",
        "-mkdir /home/ubuntu",
        "-mkdir /home/ubuntu/aerisun-backup-test",
        "-mkdir /home/ubuntu/aerisun-backup-test/site",
        "-mkdir /home/ubuntu/aerisun-backup-test/site/catalog",
        "-mkdir /home/ubuntu/aerisun-backup-test/site/catalog/probes",
    ]


def test_sftp_has_chunks_treats_unlisted_digests_as_missing(monkeypatch) -> None:
    from aerisun.domain.ops.backup_sync import SftpTransport

    existing_digest = "a" * 64
    missing_digest = "b" * 64
    captured: dict[str, str] = {}

    def fake_run(args, *, input, text, capture_output, check):
        captured["input"] = input
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="\n".join(
                [
                    f"sftp> -ls /remote/catalog/chunks/aa/aa/{existing_digest}",
                    f"/remote/catalog/chunks/aa/aa/{existing_digest}",
                    f"sftp> -ls /remote/catalog/chunks/bb/bb/{missing_digest}",
                    "",
                ]
            ),
            stderr=f'File "/remote/catalog/chunks/bb/bb/{missing_digest}" not found.\n',
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = SftpTransport(
        host="backup.example.test",
        port=22,
        username="ubuntu",
        remote_root="/remote",
        site_slug="site",
    )

    assert transport.has_chunks([existing_digest, missing_digest]) == {
        existing_digest: True,
        missing_digest: False,
    }
    assert captured["input"].splitlines() == [
        f"-ls /remote/current/catalog/chunks/aa/aa/{existing_digest}",
        f"-ls /remote/current/catalog/chunks/bb/bb/{missing_digest}",
    ]


def test_atomic_sqlite_replace_removes_stale_sidecars(tmp_path: Path) -> None:
    from aerisun.domain.ops.backup_sync import _atomic_sqlite_replace

    source = tmp_path / "source.sqlite"
    target = tmp_path / "aerisun.db"
    _write_sqlite_note(source, "backup_probe_main", "restored")
    _write_sqlite_note(target, "backup_probe_main", "destroyed")
    Path(f"{target}-wal").write_bytes(b"stale wal")
    Path(f"{target}-shm").write_bytes(b"stale shm")

    _atomic_sqlite_replace(source, target)

    assert _read_sqlite_note(target, "backup_probe_main") == "restored"
    assert not Path(f"{target}-wal").exists()
    assert not Path(f"{target}-shm").exists()


def _write_sqlite_note(path: Path, table_name: str, note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(f"create table if not exists {table_name} (id integer primary key, note text)")
        connection.execute(f"delete from {table_name}")
        connection.execute(f"insert into {table_name} (note) values (?)", (note,))
        connection.commit()


def _read_sqlite_note(path: Path, table_name: str) -> str:
    with sqlite3.connect(path) as connection:
        row = connection.execute(f"select note from {table_name} order by id asc limit 1").fetchone()
    assert row is not None
    return str(row[0])


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


def _write_runtime_sentinels(label: str, *, include_automation_pack: bool = True) -> dict[str, Path]:
    app_settings = get_settings()
    app_settings.media_dir.mkdir(parents=True, exist_ok=True)
    app_settings.secrets_dir.mkdir(parents=True, exist_ok=True)

    media_path = app_settings.media_dir / "nested" / "hello.txt"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_text(f"media-{label}", encoding="utf-8")

    secret_path = app_settings.secrets_dir / "app-secret.txt"
    secret_path.write_text(f"secret-{label}", encoding="utf-8")

    pack_path = app_settings.data_dir / "automation" / "packs" / "backup_probe_pack" / "backup-marker.txt"
    if include_automation_pack:
        pack_path.parent.mkdir(parents=True, exist_ok=True)
        pack_path.parent.joinpath("manifest.yaml").write_text(
            "\n".join(
                [
                    "key: backup_probe_pack",
                    "name: Backup Probe Pack",
                    "description: Backup fixture pack for restore tests.",
                    "enabled: false",
                    "schema_version: 2",
                    "built_in: false",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        pack_path.parent.joinpath("workflow.graph.json").write_text(
            json.dumps({"version": 2, "nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}) + "\n",
            encoding="utf-8",
        )
        pack_path.write_text(f"pack-{label}", encoding="utf-8")

    _write_sqlite_note(app_settings.db_path, "backup_probe_main", f"main-{label}")
    _write_sqlite_note(app_settings.waline_db_path, "backup_probe_waline", f"waline-{label}")
    _write_sqlite_note(app_settings.workflow_db_path, "backup_probe_workflow", f"workflow-{label}")

    return {
        "media": media_path,
        "secret": secret_path,
        "pack": pack_path,
    }


def _assert_runtime_sentinels(label: str) -> None:
    app_settings = get_settings()
    assert _read_sqlite_note(app_settings.db_path, "backup_probe_main") == f"main-{label}"
    assert _read_sqlite_note(app_settings.waline_db_path, "backup_probe_waline") == f"waline-{label}"
    assert _read_sqlite_note(app_settings.workflow_db_path, "backup_probe_workflow") == f"workflow-{label}"
    assert (app_settings.media_dir / "nested" / "hello.txt").read_text(encoding="utf-8") == f"media-{label}"
    assert (app_settings.secrets_dir / "app-secret.txt").read_text(encoding="utf-8") == f"secret-{label}"
    assert (app_settings.data_dir / "automation" / "packs" / "backup_probe_pack" / "backup-marker.txt").read_text(
        encoding="utf-8"
    ) == f"pack-{label}"


def _configure_backup(client, admin_headers, *, credential_ref: str = "default", encrypt_runtime_data: bool = True):
    app_settings = get_settings()
    _write_backup_credentials(app_settings.secrets_dir, credential_ref)

    export_response = client.post(
        f"{BASE}/backup-sync/recovery-key/export",
        headers=admin_headers,
        json={
            "credential_ref": credential_ref,
            "site_slug": "test-site",
            "passphrase": RECOVERY_PASSPHRASE,
            "rotate": False,
        },
    )
    assert export_response.status_code == 200
    export_payload = export_response.json()

    acknowledge_response = client.post(
        f"{BASE}/backup-sync/recovery-key/acknowledge",
        headers=admin_headers,
        json={"credential_ref": credential_ref},
    )
    assert acknowledge_response.status_code == 200

    update_response = client.put(
        f"{BASE}/backup-sync/config",
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
            "credential_ref": credential_ref,
            "encrypt_runtime_data": encrypt_runtime_data,
            "max_retries": 2,
            "retry_backoff_seconds": 60,
        },
    )
    assert update_response.status_code == 200
    return export_payload


def _trigger_backup(client, admin_headers) -> tuple[str, dict]:
    run_response = client.post(f"{BASE}/backup-sync/runs", headers=admin_headers)
    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    assert run_payload["commit_id"]

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    commits = commits_response.json()
    assert len(commits) == 1
    return commits[0]["id"], commits[0]


def _corrupt_first_chunk(fake_transport: FakeBackupTransport, entry: dict) -> None:
    digest = entry["chunks"][0]["digest"]
    fake_transport.chunks[digest] = b"corrupted-" + fake_transport.chunks[digest]


def _bootstrap_claim_payload(**overrides) -> dict:
    payload = {
        "remote_host": "10.129.246.56",
        "remote_port": 22,
        "remote_path": "/srv/serino-backups",
        "remote_username": "serino-backup",
        "site_slug": "aerisun",
        "credential_ref": "aerisun-backup-source",
        "ttl_minutes": 10,
    }
    payload.update(overrides)
    return payload


def _create_bootstrap_claim(client, admin_headers, **overrides) -> dict:
    response = client.post(
        f"{BASE}/backup-sync/bootstrap-claims",
        headers=admin_headers,
        json=_bootstrap_claim_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()


def _script_path(claim: dict) -> str:
    setup_url = claim["setup_url"]
    assert setup_url
    return urlparse(setup_url).path


def _result_path(claim: dict) -> str:
    token = _script_path(claim).rsplit("/", 1)[-1].removesuffix(".sh")
    return f"/api/v1/backup/setup/{token}/result"


def test_backup_bootstrap_claim_generates_safe_temporary_script(client, admin_headers) -> None:
    claim = _create_bootstrap_claim(client, admin_headers)

    assert claim["status"] == "pending"
    assert claim["setup_command"].startswith("curl -fsSL http://testserver/api/v1/backup/setup/")
    assert claim["setup_command"].endswith(" | sudo bash")
    assert "PRIVATE KEY" not in claim["setup_command"]
    assert "Authorization" not in claim["setup_command"]

    script_response = client.get(_script_path(claim))
    assert script_response.status_code == 200
    script = script_response.text
    assert "useradd --system --create-home --shell /bin/sh" in script
    assert "authorized_keys" in script
    assert 'command="internal-sftp",no-pty,no-port-forwarding,no-X11-forwarding,no-agent-forwarding' in script
    assert "ssh-ed25519 " in script
    assert "BEGIN OPENSSH PRIVATE KEY" not in script
    assert "BEGIN PRIVATE KEY" not in script
    assert "Authorization" not in script
    assert RECOVERY_PASSPHRASE not in script

    result_response = client.post(
        _result_path(claim),
        json={"status": "succeeded", "message": "connected"},
    )
    assert result_response.status_code == 200
    assert result_response.json()["status"] == "succeeded"

    second_download = client.get(_script_path(claim))
    assert second_download.status_code == 409
    second_result = client.post(_result_path(claim), json={"status": "succeeded"})
    assert second_result.status_code == 409


def test_backup_bootstrap_claim_revokes_old_pending_for_same_target(client, admin_headers) -> None:
    first = _create_bootstrap_claim(client, admin_headers)
    second = _create_bootstrap_claim(client, admin_headers)

    assert first["id"] != second["id"]
    first_status = client.get(f"{BASE}/backup-sync/bootstrap-claims/{first['id']}", headers=admin_headers)
    assert first_status.status_code == 200
    assert first_status.json()["status"] == "revoked"
    assert client.get(_script_path(first)).status_code == 409
    assert second["status"] == "pending"


def test_backup_bootstrap_claim_can_be_revoked(client, admin_headers) -> None:
    claim = _create_bootstrap_claim(client, admin_headers)
    revoke_response = client.post(
        f"{BASE}/backup-sync/bootstrap-claims/{claim['id']}/revoke",
        headers=admin_headers,
    )

    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"
    assert client.get(_script_path(claim)).status_code == 409
    assert client.post(_result_path(claim), json={"status": "succeeded"}).status_code == 409


def test_backup_bootstrap_claim_expires_after_ttl(client, admin_headers, monkeypatch) -> None:
    claim = _create_bootstrap_claim(client, admin_headers, ttl_minutes=1)
    expires_at = datetime.fromisoformat(claim["expires_at"])
    monkeypatch.setattr("aerisun.domain.ops.backup_sync._utcnow", lambda: expires_at + timedelta(seconds=1))

    assert client.get(_script_path(claim)).status_code == 409
    status_response = client.get(f"{BASE}/backup-sync/bootstrap-claims/{claim['id']}", headers=admin_headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "expired"


def test_backup_sync_endpoints_create_run_commit_and_restore(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    app_settings = get_settings()
    _write_runtime_sentinels("backup", include_automation_pack=False)
    first_key = _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    _write_runtime_sentinels("backup")

    commit_id, commit = _trigger_backup(client, admin_headers)
    assert commit["datasets"]["aerisun_db"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["waline_db"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["workflow_db"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["secrets"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["automation_packs"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["media"]["files"]
    assert commit["datasets"]["media"]["files"][0]["encryption"]["scheme"] == "x25519-aesgcm"

    backups_response = client.get(f"{BASE}/backups", headers=admin_headers)
    assert backups_response.status_code == 200
    assert backups_response.json()[0]["id"] == commit_id

    rotate_response = client.post(
        f"{BASE}/backup-sync/recovery-key/export",
        headers=admin_headers,
        json={
            "credential_ref": "default",
            "site_slug": "test-site",
            "passphrase": RECOVERY_PASSPHRASE,
            "rotate": True,
        },
    )
    assert rotate_response.status_code == 200
    assert first_key["secrets_fingerprint"] in rotate_response.json()["archived_fingerprints"]
    acknowledge_rotated_response = client.post(
        f"{BASE}/backup-sync/recovery-key/acknowledge",
        headers=admin_headers,
        json={"credential_ref": "default"},
    )
    assert acknowledge_rotated_response.status_code == 200

    queue_response = client.get("/api/v1/admin/system/backup-sync/queue", headers=admin_headers)
    assert queue_response.status_code == 200
    assert queue_response.json()[0]["status"] == "completed"

    app_settings.media_dir.joinpath("nested/hello.txt").write_text("media-damaged", encoding="utf-8")
    app_settings.secrets_dir.joinpath("app-secret.txt").write_text("secret-damaged", encoding="utf-8")
    (app_settings.data_dir / "automation" / "packs" / "backup_probe_pack" / "backup-marker.txt").write_text(
        "pack-damaged", encoding="utf-8"
    )
    app_settings.db_path.unlink(missing_ok=True)
    app_settings.waline_db_path.unlink(missing_ok=True)
    app_settings.workflow_db_path.unlink(missing_ok=True)

    started_at = time.perf_counter()
    restore_response = client.post(f"{BASE}/backup-sync/commits/{commit_id}/restore", headers=admin_headers)
    restore_elapsed = time.perf_counter() - started_at
    assert restore_response.status_code == 200
    assert restore_elapsed <= RESTORE_SPEED_LIMIT_SECONDS, f"restore took {restore_elapsed:.3f}s"
    assert restore_response.json()["restored_at"] is not None
    assert fake_transport.downloaded_chunk_batches
    _assert_runtime_sentinels("backup")
    assert (app_settings.secrets_dir / "backup-sync" / "default" / "secrets_x25519.pem").exists()
    assert (
        app_settings.secrets_dir
        / "backup-sync"
        / "default"
        / "archived"
        / first_key["secrets_fingerprint"]
        / "secrets_x25519.pem"
    ).exists()
    rerun_response = client.post(f"{BASE}/backup-sync/runs", headers=admin_headers)
    assert rerun_response.status_code == 201
    assert rerun_response.json()["status"] == "completed"


@pytest.mark.parametrize(
    ("dataset_key", "expected_detail"),
    [
        ("aerisun_db", "Downloaded backup chunk digest mismatch"),
        ("media", "Downloaded backup chunk digest mismatch"),
    ],
)
def test_backup_restore_corrupt_chunk_fails_before_replacing_runtime_data(
    client, admin_headers, monkeypatch, dataset_key: str, expected_detail: str
) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    _write_runtime_sentinels("backup", include_automation_pack=False)
    _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    _write_runtime_sentinels("backup")
    commit_id, commit = _trigger_backup(client, admin_headers)

    _write_runtime_sentinels("live")
    if dataset_key == "media":
        _corrupt_first_chunk(fake_transport, commit["datasets"]["media"]["files"][0])
    else:
        _corrupt_first_chunk(fake_transport, commit["datasets"][dataset_key])

    restore_response = client.post(f"{BASE}/backup-sync/commits/{commit_id}/restore", headers=admin_headers)
    assert restore_response.status_code == 422
    assert expected_detail in restore_response.json()["detail"]
    _assert_runtime_sentinels("live")


def test_backup_sync_config_test_endpoint_reports_connectivity(client, admin_headers, monkeypatch) -> None:
    timeouts: list[tuple[str, int | None]] = []

    def fake_begin_session(self, *, timeout_seconds=None):
        timeouts.append(("begin_session", timeout_seconds))
        return {"session_id": "s", "site_slug": "test-site"}

    def fake_probe_write_access(self, *, timeout_seconds=None):
        timeouts.append(("probe_write_access", timeout_seconds))

    monkeypatch.setattr(
        "aerisun.domain.ops.backup_sync.SftpTransport.begin_session",
        fake_begin_session,
    )
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.SftpTransport.probe_write_access", fake_probe_write_access)
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.SftpTransport.fetch_repo_identity", lambda self: None)

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
    assert payload["remote_path_preview"] == "/srv/serino-backups"
    assert payload["remote_history_state"] == "empty"
    assert payload["recovery_key_ready"] is False
    assert payload["recovery_key_acknowledged"] is False
    assert timeouts == [("begin_session", 3), ("probe_write_access", 3)]


def test_backup_machine_connection_probe_is_fast_and_read_only(client, admin_headers, monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("quick probe must not create a session or write probe files")

    monkeypatch.setattr("aerisun.domain.ops.backup_sync.SftpTransport.begin_session", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.SftpTransport.probe_write_access", forbidden)
    monkeypatch.setattr(
        "aerisun.domain.ops.backup_sync.SftpTransport.probe_repo_identity",
        lambda self, timeout_seconds=3: (
            False,
            None,
            "无法使用 serino-backup 快速连接备份机，需要执行临时接入命令。",
        ),
    )

    response = client.post(
        "/api/v1/admin/system/backup-sync/connection/probe",
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
    assert payload["ok"] is False
    assert payload["remote_history_state"] == "unreachable"
    assert "临时命令" in payload["summary"]


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
    assert "恢复密码" in response.json()["detail"]


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
    assert "确认恢复密码" in response.json()["detail"]


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
