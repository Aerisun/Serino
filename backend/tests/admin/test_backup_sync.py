from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import ValidationError

BASE = "/api/v1/admin/system"
RECOVERY_PASSPHRASE = "correct horse battery staple"
RESTORE_SPEED_LIMIT_SECONDS = 5.0


class FakeBackupTransport:
    def __init__(self) -> None:
        self.chunks: dict[str, bytes] = {}
        self.manifests: dict[str, dict] = {}
        self.commits: dict[str, dict] = {}
        self.downloaded_chunk_batches: list[list[str]] = []
        self.deleted_chunks: list[str] = []
        self.deleted_manifests: list[str] = []
        self.deleted_commits: list[str] = []
        self.fail_delete_commits: set[str] = set()
        self.fail_delete_chunks: set[str] = set()
        self.repo_identity: dict | None = None
        self.recovery_keyring: dict | None = None

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

    def delete_chunk(self, digest: str) -> None:
        if digest in self.fail_delete_chunks:
            raise RuntimeError(f"cannot delete remote chunk {digest}")
        self.deleted_chunks.append(digest)
        self.chunks.pop(digest, None)

    def delete_manifest(self, digest: str) -> None:
        self.deleted_manifests.append(digest)
        self.manifests.pop(digest, None)

    def delete_commit(self, commit_id: str, *, created_at: str, backup_path: str | None = None) -> None:
        if commit_id in self.fail_delete_commits:
            raise RuntimeError(f"cannot delete remote commit {commit_id}")
        self.deleted_commits.append(commit_id)
        self.commits.pop(commit_id, None)

    def download_chunks(self, digests: list[str], destination_dir: Path) -> dict[str, Path]:
        self.downloaded_chunk_batches.append(list(digests))
        destination_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        for digest in digests:
            path = destination_dir / digest
            path.write_bytes(self.chunks[digest])
            paths[digest] = path
        return paths

    def fetch_repo_identity(self) -> dict | None:
        return self.repo_identity

    def write_repo_identity(self, payload: dict) -> None:
        self.repo_identity = dict(payload)

    def fetch_recovery_keyring(self) -> dict | None:
        return self.recovery_keyring

    def write_recovery_keyring(self, payload: dict) -> None:
        self.recovery_keyring = json.loads(json.dumps(payload))


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


def test_sftp_fetch_recovery_keyring_reports_connection_failure(monkeypatch) -> None:
    from aerisun.domain.ops.backup_sync import SftpTransport

    def fake_run(args, *, input, text, capture_output, check):
        return subprocess.CompletedProcess(args, 255, "", "Permission denied (publickey).")

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = SftpTransport(
        host="backup.example.test",
        port=22,
        username="serino-backup",
        remote_root="/srv/serino-backups",
        site_slug="site",
    )

    with pytest.raises(ValidationError, match="无法使用 serino-backup"):
        transport.fetch_recovery_keyring()


def test_sftp_delete_commit_reports_index_delete_failure(monkeypatch) -> None:
    from aerisun.domain.ops.backup_sync import SftpTransport

    def fake_run(args, *, input, text, capture_output, check):
        assert "rm /remote/current/catalog/commit-index/commit-1.json" in input
        return subprocess.CompletedProcess(args, 255, "", "Permission denied")

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = SftpTransport(
        host="backup.example.test",
        port=22,
        username="serino-backup",
        remote_root="/remote",
        site_slug="site",
    )

    with pytest.raises(ValidationError, match="Permission denied"):
        transport.delete_commit("commit-1", created_at="2026-07-03T00:00:00+08:00")


def test_sftp_delete_commit_uses_stored_backup_path_for_marker(monkeypatch) -> None:
    from aerisun.domain.ops.backup_sync import SftpTransport

    batches: list[str] = []

    def fake_run(args, *, input, text, capture_output, check):
        batches.append(input)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = SftpTransport(
        host="backup.example.test",
        port=22,
        username="serino-backup",
        remote_root="/remote",
        site_slug="site",
    )

    transport.delete_commit(
        "commit-1",
        created_at="2026-07-03T00:00:00+08:00",
        backup_path="/remote/current/commits/2026/07/03/20260703T000005Z-commit-1/manifest.json",
    )

    assert batches == [
        "rm /remote/current/catalog/commit-index/commit-1.json\n",
        "rm /remote/current/commits/2026/07/03/20260703T000005Z-commit-1/manifest.json\n",
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


def _configure_backup(
    client,
    admin_headers,
    *,
    credential_ref: str = "default",
    encrypt_runtime_data: bool = True,
    max_retention_count: int = 0,
    retention_days: int | None = None,
):
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
            "max_retention_count": max_retention_count,
            **({} if retention_days is None else {"retention_days": retention_days}),
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


def _trigger_backup_and_read_commit(client, admin_headers) -> tuple[str, dict]:
    run_response = client.post(f"{BASE}/backup-sync/runs", headers=admin_headers)
    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    commit_id = run_payload["commit_id"]
    assert commit_id

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    commit = next(item for item in commits_response.json() if item["id"] == commit_id)
    return commit_id, commit


def _remote_history_import_payload(*, passphrase: str = RECOVERY_PASSPHRASE, commit_id: str | None = None) -> dict:
    payload = {
        "config": {
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
        "passphrase": passphrase,
    }
    if commit_id is not None:
        payload["commit_id"] = commit_id
    return payload


def _corrupt_first_chunk(fake_transport: FakeBackupTransport, entry: dict) -> None:
    digest = entry["chunks"][0]["digest"]
    fake_transport.chunks[digest] = b"corrupted-" + fake_transport.chunks[digest]


def _commit_chunk_digests(commit: dict) -> set[str]:
    from aerisun.domain.ops.backup_sync import _manifest_chunk_digests

    return set(_manifest_chunk_digests({"datasets": commit["datasets"]}))


def _capture_retention_cleanup_schedule(monkeypatch):
    from aerisun.domain.ops import backup_sync

    scheduled_cleanups: list[str] = []
    monkeypatch.setattr(
        backup_sync,
        "schedule_backup_retention_cleanup",
        lambda: scheduled_cleanups.append("cleanup"),
        raising=False,
    )
    return backup_sync, scheduled_cleanups


def _media_chunk_digests(commit: dict, relative_path: str) -> set[str]:
    for entry in commit["datasets"]["media"]["files"]:
        if entry["path"] == relative_path:
            return {chunk["digest"] for chunk in entry["chunks"]}
    raise AssertionError(f"media file not found in backup manifest: {relative_path}")


def test_trigger_backup_sync_uses_queue_item_id_before_dispatch(monkeypatch) -> None:
    from aerisun.domain.ops import backup_sync

    dispatch_started = False

    class DetachedAfterDispatchQueueItem:
        @property
        def id(self) -> str:
            if dispatch_started:
                raise AssertionError("queue item id was read after dispatch detached the object")
            return "queue-1"

    class FakeSession:
        def expire_all(self) -> None:
            pass

        def refresh(self, _item) -> None:
            pass

    created_at = datetime(2026, 1, 1)
    run = SimpleNamespace(
        id="run-1",
        job_name="backup-sync",
        status="completed",
        transport="sftp",
        trigger_kind="manual",
        queue_item_id="queue-1",
        commit_id="commit-1",
        stats_json={},
        retry_count=0,
        next_retry_at=None,
        last_error=None,
        started_at=None,
        finished_at=created_at,
        message="Backup sync completed",
        created_at=created_at,
        updated_at=created_at,
    )

    def fake_dispatch_backup_sync():
        nonlocal dispatch_started
        dispatch_started = True

    monkeypatch.setattr(
        backup_sync, "ensure_backup_queue_item", lambda session, trigger_kind, force: DetachedAfterDispatchQueueItem()
    )
    monkeypatch.setattr(backup_sync, "dispatch_backup_sync", fake_dispatch_backup_sync)
    monkeypatch.setattr(backup_sync.repo, "get_backup_queue_item", lambda session, queue_item_id: object())
    monkeypatch.setattr(backup_sync.repo, "list_sync_runs", lambda session: [run])

    payload = backup_sync.trigger_backup_sync(FakeSession())

    assert payload.id == "run-1"


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
    assert "备份机已成功连接！" in script
    assert "请您返回后台管理界面稍等片刻，那边正在检测..." in script
    assert "Backup machine is connected." not in script
    assert "Test and Start Backup" not in script

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
    runtime_file = app_settings.data_dir / "data" / "custom-runtime" / "settings.json"
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    runtime_file.write_text(json.dumps({"label": "runtime-backup"}) + "\n", encoding="utf-8")
    runtime_stale_file = app_settings.data_dir / "data" / "custom-runtime" / "stale-after-backup.json"

    commit_id, commit = _trigger_backup(client, admin_headers)
    assert commit["datasets"]["aerisun_db"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["waline_db"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["workflow_db"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["secrets"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["automation_packs"]["encryption"]["scheme"] == "x25519-aesgcm"
    assert commit["datasets"]["runtime_files"]["encryption"]["scheme"] == "x25519-aesgcm"
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
    runtime_file.write_text(json.dumps({"label": "runtime-damaged"}) + "\n", encoding="utf-8")
    runtime_stale_file.write_text(json.dumps({"label": "runtime-stale"}) + "\n", encoding="utf-8")
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
    assert json.loads(runtime_file.read_text(encoding="utf-8")) == {"label": "runtime-backup"}
    assert not runtime_stale_file.exists()
    restored_commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert restored_commits_response.status_code == 200
    restored_commits = restored_commits_response.json()
    assert len(restored_commits) == 1
    assert restored_commits[0]["id"] == commit_id
    assert restored_commits[0]["restored_at"] is not None
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


def test_rotating_backup_recovery_key_keeps_existing_remote_history_current(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)
    monkeypatch.setattr(
        "aerisun.domain.ops.backup_sync.SftpTransport.begin_session",
        lambda self, timeout_seconds=None: {"session_id": "fake-session", "site_slug": "test-site"},
    )
    monkeypatch.setattr(
        "aerisun.domain.ops.backup_sync.SftpTransport.probe_write_access",
        lambda self, timeout_seconds=None: None,
    )
    monkeypatch.setattr(
        "aerisun.domain.ops.backup_sync.SftpTransport.fetch_repo_identity",
        lambda self: fake_transport.fetch_repo_identity(),
    )

    first_key = _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    _write_runtime_sentinels("rotation-before")
    first_commit_id, _first_commit = _trigger_backup(client, admin_headers)
    original_repo_id = fake_transport.repo_identity["repo_id"]

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
    acknowledge_response = client.post(
        f"{BASE}/backup-sync/recovery-key/acknowledge",
        headers=admin_headers,
        json={"credential_ref": "default"},
    )
    assert acknowledge_response.status_code == 200

    test_response = client.post(
        f"{BASE}/backup-sync/config/test",
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
    assert test_response.status_code == 200
    assert test_response.json()["remote_history_state"] == "current"

    _write_runtime_sentinels("rotation-after")
    run_response = client.post(f"{BASE}/backup-sync/runs", headers=admin_headers)
    assert run_response.status_code == 201
    assert run_response.json()["status"] == "completed"
    assert run_response.json()["commit_id"] != first_commit_id
    assert fake_transport.repo_identity["repo_id"] == original_repo_id
    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    assert len(commits_response.json()) == 2


def test_remote_history_import_restores_with_recovery_password_without_local_key(
    client, admin_headers, monkeypatch
) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    app_settings = get_settings()
    _write_runtime_sentinels("remote-history", include_automation_pack=False)
    _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    _write_runtime_sentinels("remote-history")
    commit_id, _commit = _trigger_backup(client, admin_headers)
    assert fake_transport.recovery_keyring is not None

    reset_response = client.post(f"{BASE}/backup-sync/reset", headers=admin_headers)
    assert reset_response.status_code == 200
    assert not (app_settings.secrets_dir / "backup-sync" / "default" / "secrets_x25519.pem").exists()
    _write_runtime_sentinels("damaged")

    wrong_password_response = client.post(
        f"{BASE}/backup-sync/remote-history/import/preview",
        headers=admin_headers,
        json=_remote_history_import_payload(passphrase="wrong password"),
    )
    assert wrong_password_response.status_code == 422
    assert "恢复密码" in wrong_password_response.json()["detail"]

    preview_response = client.post(
        f"{BASE}/backup-sync/remote-history/import/preview",
        headers=admin_headers,
        json=_remote_history_import_payload(),
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["remote_repo_id"] == fake_transport.repo_identity["repo_id"]
    assert preview_payload["key_fingerprints"]
    assert preview_payload["commits"][0]["id"] == commit_id

    restore_response = client.post(
        f"{BASE}/backup-sync/remote-history/import/restore",
        headers=admin_headers,
        json=_remote_history_import_payload(commit_id=commit_id),
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["id"] == commit_id
    assert restore_response.json()["restored_at"] is not None
    _assert_runtime_sentinels("remote-history")
    assert (app_settings.secrets_dir / "backup-sync" / "default" / "secrets_x25519.pem").exists()

    restored_commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert restored_commits_response.status_code == 200
    restored_commits = restored_commits_response.json()
    assert len(restored_commits) == 1
    assert restored_commits[0]["id"] == commit_id
    assert restored_commits[0]["restored_at"] is not None


def test_remote_history_import_backfills_missing_keyring_from_original_service(
    client, admin_headers, monkeypatch
) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    _write_runtime_sentinels("legacy-remote")
    _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    commit_id, _commit = _trigger_backup(client, admin_headers)

    fake_transport.recovery_keyring = None
    preview_response = client.post(
        f"{BASE}/backup-sync/remote-history/import/preview",
        headers=admin_headers,
        json=_remote_history_import_payload(),
    )

    assert preview_response.status_code == 200
    assert fake_transport.recovery_keyring is not None
    preview_payload = preview_response.json()
    assert preview_payload["key_fingerprints"]
    assert preview_payload["commits"][0]["id"] == commit_id


def test_remote_history_import_does_not_backfill_keyring_for_foreign_local_key(
    client, admin_headers, monkeypatch
) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    _write_runtime_sentinels("foreign-legacy-remote")
    _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    _trigger_backup(client, admin_headers)

    fake_transport.recovery_keyring = None
    fake_transport.repo_identity["repo_id"] = "foreign-repo-id"
    preview_response = client.post(
        f"{BASE}/backup-sync/remote-history/import/preview",
        headers=admin_headers,
        json=_remote_history_import_payload(),
    )

    assert preview_response.status_code == 422
    assert "不匹配" in preview_response.json()["detail"]
    assert fake_transport.recovery_keyring is None


def test_remote_history_import_reports_unrecoverable_legacy_history_without_local_key(
    client, admin_headers, monkeypatch
) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    _write_runtime_sentinels("legacy-without-keyring")
    _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    _trigger_backup(client, admin_headers)

    reset_response = client.post(f"{BASE}/backup-sync/reset", headers=admin_headers)
    assert reset_response.status_code == 200
    fake_transport.recovery_keyring = None

    preview_response = client.post(
        f"{BASE}/backup-sync/remote-history/import/preview",
        headers=admin_headers,
        json=_remote_history_import_payload(),
    )

    assert preview_response.status_code == 422
    detail = preview_response.json()["detail"]
    assert "不能仅凭密码恢复" in detail
    assert "请先设置恢复密码，然后再创建备份" not in detail


def test_initializing_new_remote_history_discards_local_backup_history(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    _write_runtime_sentinels("old-local-history")
    _configure_backup(client, admin_headers, encrypt_runtime_data=True)
    _trigger_backup(client, admin_headers)
    fake_transport.repo_identity = None

    before_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert before_response.status_code == 200
    assert len(before_response.json()) == 1

    overwrite_response = client.post(
        f"{BASE}/backup-sync/remote-history/overwrite",
        headers=admin_headers,
        json=_remote_history_import_payload()["config"],
    )

    assert overwrite_response.status_code == 200
    payload = overwrite_response.json()
    assert payload["remote_history_state"] == "current"
    assert fake_transport.repo_identity is not None
    after_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert after_response.status_code == 200
    assert after_response.json() == []
    config_response = client.get(f"{BASE}/backup-sync/config", headers=admin_headers)
    assert config_response.status_code == 200
    assert config_response.json()["recovery_key_ready"] is True


def test_backup_sync_config_defaults_to_daily_schedule_and_sixty_day_retention(client, admin_headers) -> None:
    response = client.get(f"{BASE}/backup-sync/config", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["interval_minutes"] == 1440
    assert payload["max_retention_count"] == 80
    assert payload["retention_days"] == 60


def test_backup_sync_reset_restores_retention_defaults(client, admin_headers) -> None:
    _configure_backup(
        client,
        admin_headers,
        encrypt_runtime_data=False,
        max_retention_count=0,
        retention_days=0,
    )

    response = client.post(f"{BASE}/backup-sync/reset", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()["config"]
    assert payload["interval_minutes"] == 1440
    assert payload["max_retention_count"] == 80
    assert payload["retention_days"] == 60


def test_retention_prunes_remote_manifest_and_unreferenced_chunks(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)
    backup_sync, scheduled_cleanups = _capture_retention_cleanup_schedule(monkeypatch)

    app_settings = get_settings()
    _write_runtime_sentinels("retention-one")
    stable_media = app_settings.media_dir / "stable.bin"
    stable_media.write_bytes(b"shared-media-payload")
    _configure_backup(client, admin_headers, encrypt_runtime_data=False, max_retention_count=1)

    first_commit_id, first_commit = _trigger_backup(client, admin_headers)
    first_manifest_digest = first_commit["manifest_digest"]
    first_chunks = _commit_chunk_digests(first_commit)

    _write_runtime_sentinels("retention-two")
    stable_media.write_bytes(b"shared-media-payload")
    second_commit_id, second_commit = _trigger_backup_and_read_commit(client, admin_headers)
    second_chunks = _commit_chunk_digests(second_commit)

    assert second_commit_id != first_commit_id
    assert scheduled_cleanups == ["cleanup"]
    assert fake_transport.deleted_commits == []

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    commits = commits_response.json()
    assert [commit["id"] for commit in commits] == [second_commit_id, first_commit_id]

    backup_sync._run_backup_retention_cleanup()

    assert first_commit_id in fake_transport.deleted_commits
    assert first_commit_id not in fake_transport.commits
    assert first_manifest_digest in fake_transport.deleted_manifests
    assert first_manifest_digest not in fake_transport.manifests

    first_only_chunks = first_chunks - second_chunks
    shared_chunks = first_chunks & second_chunks
    assert first_only_chunks
    assert shared_chunks
    assert first_only_chunks <= set(fake_transport.deleted_chunks)
    assert all(digest not in fake_transport.chunks for digest in first_only_chunks)
    assert all(digest in fake_transport.chunks for digest in shared_chunks)

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    commits = commits_response.json()
    assert [commit["id"] for commit in commits] == [second_commit_id]


def test_retention_prunes_backups_older_than_configured_days(client, admin_headers, monkeypatch) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.ops import backup_sync
    from aerisun.domain.ops.models import BackupCommit

    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)
    scheduled_cleanups: list[str] = []
    monkeypatch.setattr(
        backup_sync,
        "schedule_backup_retention_cleanup",
        lambda: scheduled_cleanups.append("cleanup"),
        raising=False,
    )

    app_settings = get_settings()
    now = datetime(2026, 7, 5, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    current_time = {"value": now - timedelta(days=61)}
    monkeypatch.setattr(backup_sync, "_utcnow", lambda: current_time["value"])

    _write_runtime_sentinels("retention-age-old")
    stable_media = app_settings.media_dir / "stable.bin"
    stable_media.write_bytes(b"shared-media-payload")
    _configure_backup(client, admin_headers, encrypt_runtime_data=False, max_retention_count=0)

    old_commit_id, old_commit = _trigger_backup_and_read_commit(client, admin_headers)
    old_manifest_digest = old_commit["manifest_digest"]
    old_chunks = _commit_chunk_digests(old_commit)
    with get_session_factory()() as session:
        old_record = session.get(BackupCommit, old_commit_id)
        assert old_record is not None
        old_record.created_at = current_time["value"]
        old_record.updated_at = current_time["value"]
        session.commit()

    current_time["value"] = now
    _write_runtime_sentinels("retention-age-new")
    stable_media.write_bytes(b"shared-media-payload")
    new_commit_id, new_commit = _trigger_backup_and_read_commit(client, admin_headers)
    new_chunks = _commit_chunk_digests(new_commit)

    assert new_commit_id != old_commit_id
    assert scheduled_cleanups == ["cleanup"]
    assert old_commit_id in fake_transport.commits

    backup_sync._run_backup_retention_cleanup()

    assert old_commit_id in fake_transport.deleted_commits
    assert old_commit_id not in fake_transport.commits
    assert old_manifest_digest in fake_transport.deleted_manifests
    assert old_manifest_digest not in fake_transport.manifests

    old_only_chunks = old_chunks - new_chunks
    shared_chunks = old_chunks & new_chunks
    assert old_only_chunks
    assert shared_chunks
    assert old_only_chunks <= set(fake_transport.deleted_chunks)
    assert all(digest not in fake_transport.chunks for digest in old_only_chunks)
    assert all(digest in fake_transport.chunks for digest in shared_chunks)

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    assert [commit["id"] for commit in commits_response.json()] == [new_commit_id]


def test_retention_prunes_existing_backups_when_limit_is_lowered(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)
    backup_sync, scheduled_cleanups = _capture_retention_cleanup_schedule(monkeypatch)

    _write_runtime_sentinels("retention-config-one")
    _configure_backup(
        client,
        admin_headers,
        encrypt_runtime_data=False,
        max_retention_count=0,
        retention_days=0,
    )
    first_commit_id, _ = _trigger_backup_and_read_commit(client, admin_headers)

    _write_runtime_sentinels("retention-config-two")
    second_commit_id, _ = _trigger_backup_and_read_commit(client, admin_headers)

    _write_runtime_sentinels("retention-config-three")
    third_commit_id, third_commit = _trigger_backup_and_read_commit(client, admin_headers)

    update_response = client.put(
        f"{BASE}/backup-sync/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "paused": False,
            "interval_minutes": 1440,
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
            "max_retention_count": 1,
            "retention_days": 0,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["max_retention_count"] == 1
    assert scheduled_cleanups == ["cleanup"]
    assert fake_transport.deleted_commits == []
    assert first_commit_id in fake_transport.commits
    assert second_commit_id in fake_transport.commits
    assert third_commit_id in fake_transport.commits

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    assert [commit["id"] for commit in commits_response.json()] == [
        third_commit_id,
        second_commit_id,
        first_commit_id,
    ]

    backup_sync._run_backup_retention_cleanup()

    assert first_commit_id in fake_transport.deleted_commits
    assert second_commit_id in fake_transport.deleted_commits
    assert third_commit_id not in fake_transport.deleted_commits
    assert first_commit_id not in fake_transport.commits
    assert second_commit_id not in fake_transport.commits
    assert third_commit_id in fake_transport.commits
    assert third_commit["manifest_digest"] in fake_transport.manifests

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    assert [commit["id"] for commit in commits_response.json()] == [third_commit_id]


def test_restore_prunes_remote_commits_after_restored_point(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)

    app_settings = get_settings()
    _write_runtime_sentinels("restore-prune-one")
    stable_media = app_settings.media_dir / "stable.bin"
    stable_media.write_bytes(b"shared-media-payload")
    _configure_backup(client, admin_headers, encrypt_runtime_data=False, max_retention_count=0, retention_days=0)
    first_commit_id, first_commit = _trigger_backup_and_read_commit(client, admin_headers)

    _write_runtime_sentinels("restore-prune-two")
    stable_media.write_bytes(b"shared-media-payload")
    restore_commit_id, restore_commit = _trigger_backup_and_read_commit(client, admin_headers)

    _write_runtime_sentinels("restore-prune-three")
    stable_media.write_bytes(b"shared-media-payload")
    future_commit_id, future_commit = _trigger_backup_and_read_commit(client, admin_headers)
    future_manifest_digest = future_commit["manifest_digest"]

    protected_chunks = _commit_chunk_digests(first_commit) | _commit_chunk_digests(restore_commit)
    future_chunks = _commit_chunk_digests(future_commit)
    future_only_chunks = future_chunks - protected_chunks
    shared_chunks = future_chunks & protected_chunks
    assert future_only_chunks
    assert shared_chunks

    restore_response = client.post(f"{BASE}/backup-sync/commits/{restore_commit_id}/restore", headers=admin_headers)

    assert restore_response.status_code == 200
    assert future_commit_id in fake_transport.deleted_commits
    assert future_commit_id not in fake_transport.commits
    assert future_manifest_digest in fake_transport.deleted_manifests
    assert future_manifest_digest not in fake_transport.manifests
    assert future_only_chunks <= set(fake_transport.deleted_chunks)
    assert all(digest not in fake_transport.chunks for digest in future_only_chunks)
    assert all(digest in fake_transport.chunks for digest in shared_chunks)

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    assert [commit["id"] for commit in commits_response.json()] == [restore_commit_id, first_commit_id]


def test_retention_keeps_history_when_remote_commit_delete_fails(client, admin_headers, monkeypatch) -> None:
    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)
    backup_sync, scheduled_cleanups = _capture_retention_cleanup_schedule(monkeypatch)

    _write_runtime_sentinels("retention-fail-one")
    _configure_backup(client, admin_headers, encrypt_runtime_data=False, max_retention_count=1)
    first_commit_id, first_commit = _trigger_backup(client, admin_headers)
    first_manifest_digest = first_commit["manifest_digest"]
    first_chunks = _commit_chunk_digests(first_commit)
    fake_transport.fail_delete_commits.add(first_commit_id)

    _write_runtime_sentinels("retention-fail-two")
    second_run_response = client.post(f"{BASE}/backup-sync/runs", headers=admin_headers)
    assert second_run_response.status_code == 201
    assert second_run_response.json()["status"] == "completed"
    assert scheduled_cleanups == ["cleanup"]

    backup_sync._run_backup_retention_cleanup()

    commits_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert commits_response.status_code == 200
    commit_ids = {commit["id"] for commit in commits_response.json()}
    assert first_commit_id in commit_ids
    assert second_run_response.json()["commit_id"] in commit_ids

    assert first_commit_id in fake_transport.commits
    assert first_manifest_digest in fake_transport.manifests
    assert first_manifest_digest not in fake_transport.deleted_manifests
    assert all(digest in fake_transport.chunks for digest in first_chunks)
    assert not (first_chunks & set(fake_transport.deleted_chunks))


def test_retention_retries_hidden_object_cleanup_after_chunk_delete_failure(client, admin_headers, monkeypatch) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.ops import backup_sync
    from aerisun.domain.ops.models import BackupCommit

    fake_transport = FakeBackupTransport()
    monkeypatch.setattr("aerisun.domain.ops.backup_sync.build_transport", lambda config, credentials: fake_transport)
    scheduled_cleanups: list[str] = []
    monkeypatch.setattr(
        backup_sync,
        "schedule_backup_retention_cleanup",
        lambda: scheduled_cleanups.append("cleanup"),
        raising=False,
    )

    _write_runtime_sentinels("retention-retry-one")
    _configure_backup(client, admin_headers, encrypt_runtime_data=False, max_retention_count=1)
    first_commit_id, first_commit = _trigger_backup(client, admin_headers)
    blocked_chunk = next(iter(_media_chunk_digests(first_commit, "media/nested/hello.txt")))
    fake_transport.fail_delete_chunks.add(blocked_chunk)

    _write_runtime_sentinels("retention-retry-two")
    second_run_response = client.post(f"{BASE}/backup-sync/runs", headers=admin_headers)
    assert second_run_response.status_code == 201
    assert scheduled_cleanups == ["cleanup"]

    visible_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert visible_response.status_code == 200
    assert [commit["id"] for commit in visible_response.json()] == [
        second_run_response.json()["commit_id"],
        first_commit_id,
    ]

    backup_sync._run_backup_retention_cleanup()

    visible_response = client.get(f"{BASE}/backup-sync/commits", headers=admin_headers)
    assert visible_response.status_code == 200
    assert [commit["id"] for commit in visible_response.json()] == [second_run_response.json()["commit_id"]]
    assert blocked_chunk not in _commit_chunk_digests(visible_response.json()[0])
    assert blocked_chunk in fake_transport.chunks

    with get_session_factory()() as session:
        hidden = session.get(BackupCommit, first_commit_id)
        assert hidden is not None
        assert hidden.trigger_kind == backup_sync.BACKUP_RETENTION_TOMBSTONE_TRIGGER

        config = backup_sync.get_or_create_backup_sync_config(session)
        fake_transport.fail_delete_chunks.clear()
        backup_sync._enforce_retention(config, fake_transport)
        session.expire_all()
        assert session.get(BackupCommit, first_commit_id) is None

    assert blocked_chunk in fake_transport.deleted_chunks
    assert blocked_chunk not in fake_transport.chunks


@pytest.mark.parametrize(
    ("dataset_key", "expected_detail"),
    [
        ("aerisun_db", "Downloaded backup chunk digest mismatch"),
        ("runtime_files", "Downloaded backup chunk digest mismatch"),
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
