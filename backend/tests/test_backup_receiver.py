from __future__ import annotations

import base64
import hashlib
import importlib
import json
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "companions" / "backup-receiver" / "src"))

backup_receiver = importlib.import_module("backup_receiver")
BackupReceiverSettings = backup_receiver.BackupReceiverSettings
create_app = backup_receiver.create_app


def _sign_headers(
    private_key: ed25519.Ed25519PrivateKey,
    *,
    site_slug: str,
    key_fingerprint: str,
    method: str,
    path: str,
    body: bytes,
    session_id: str | None = None,
) -> dict[str, str]:
    timestamp = str(int(time.time()))
    body_digest = hashlib.sha256(body).hexdigest()
    message = "\n".join([method.upper(), path, site_slug, timestamp, body_digest]).encode("utf-8")
    signature = private_key.sign(message)
    headers = {
        "X-Backup-Site": site_slug,
        "X-Backup-Key": key_fingerprint,
        "X-Backup-Timestamp": timestamp,
        "X-Backup-Signature": base64.b64encode(signature).decode("ascii"),
    }
    if session_id is not None:
        headers["X-Backup-Session"] = session_id
    return headers


def _json_headers(
    private_key: ed25519.Ed25519PrivateKey,
    *,
    site_slug: str,
    key_fingerprint: str,
    method: str,
    path: str,
    body: bytes,
    session_id: str | None = None,
) -> dict[str, str]:
    headers = _sign_headers(
        private_key,
        site_slug=site_slug,
        key_fingerprint=key_fingerprint,
        method=method,
        path=path,
        body=body,
        session_id=session_id,
    )
    headers["content-type"] = "application/json"
    return headers


def test_receiver_session_chunk_manifest_and_commit_flow(tmp_path) -> None:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_fingerprint = hashlib.sha256(public_bytes).hexdigest()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    app = create_app(
        BackupReceiverSettings(
            data_dir=tmp_path / "receiver-store",
            allowed_public_keys={"test-site": {key_fingerprint: pem}},
        )
    )
    client = TestClient(app)

    session_body = json.dumps({"site_slug": "test-site"}).encode("utf-8")
    session_response = client.post(
        "/v1/sessions",
        content=session_body,
        headers=_json_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="POST",
            path="/v1/sessions",
            body=session_body,
        ),
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    chunk_body = b"receiver-chunk-payload"
    digest = hashlib.sha256(chunk_body).hexdigest()
    chunk_response = client.put(
        f"/v1/chunks/{digest}",
        content=chunk_body,
        headers=_sign_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="PUT",
            path=f"/v1/chunks/{digest}",
            body=chunk_body,
            session_id=session_id,
        ),
    )
    assert chunk_response.status_code == 204

    manifest = {
        "created_at": "2026-03-29T00:00:00+00:00",
        "datasets": {
            "aerisun_db": {"chunks": [{"digest": digest, "size": len(chunk_body)}]},
            "waline_db": {"chunks": [{"digest": digest, "size": len(chunk_body)}]},
            "secrets": {"chunks": [{"digest": digest, "size": len(chunk_body)}]},
            "media": {"files": [{"chunks": [{"digest": digest, "size": len(chunk_body)}]}]},
        },
    }
    manifest_body = json.dumps(manifest).encode("utf-8")
    manifest_digest = hashlib.sha256(manifest_body).hexdigest()
    manifest_response = client.put(
        f"/v1/manifests/{manifest_digest}",
        content=manifest_body,
        headers=_json_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="PUT",
            path=f"/v1/manifests/{manifest_digest}",
            body=manifest_body,
            session_id=session_id,
        ),
    )
    assert manifest_response.status_code == 204

    commit_body = json.dumps(
        {"commit_id": "8fd99dd1-7a81-4c6f-b08b-659b176ad03f", "manifest_digest": manifest_digest, "manifest": manifest}
    ).encode("utf-8")
    commit_response = client.post(
        "/v1/commits",
        content=commit_body,
        headers=_json_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="POST",
            path="/v1/commits",
            body=commit_body,
            session_id=session_id,
        ),
    )
    assert commit_response.status_code == 200

    list_response = client.get(
        "/v1/commits",
        headers=_sign_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="GET",
            path="/v1/commits",
            body=b"",
            session_id=session_id,
        ),
    )
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["commit_id"] == "8fd99dd1-7a81-4c6f-b08b-659b176ad03f"

    download_response = client.get(
        f"/v1/chunks/{digest}/download",
        headers=_sign_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="GET",
            path=f"/v1/chunks/{digest}/download",
            body=b"",
            session_id=session_id,
        ),
    )
    assert download_response.status_code == 200
    assert download_response.content == chunk_body


def test_receiver_rejects_commit_with_missing_chunk(tmp_path) -> None:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    key_fingerprint = hashlib.sha256(
        public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    ).hexdigest()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    app = create_app(
        BackupReceiverSettings(
            data_dir=tmp_path / "receiver-store",
            allowed_public_keys={"test-site": {key_fingerprint: pem}},
        )
    )
    client = TestClient(app)

    session_body = json.dumps({"site_slug": "test-site"}).encode("utf-8")
    session_id = client.post(
        "/v1/sessions",
        content=session_body,
        headers=_json_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="POST",
            path="/v1/sessions",
            body=session_body,
        ),
    ).json()["session_id"]

    manifest = {
        "created_at": "2026-03-29T00:00:00+00:00",
        "datasets": {
            "aerisun_db": {"chunks": [{"digest": "a" * 64, "size": 1}]},
            "waline_db": {"chunks": []},
            "secrets": {"chunks": []},
            "media": {"files": []},
        },
    }
    manifest_body = json.dumps(manifest).encode("utf-8")
    manifest_digest = hashlib.sha256(manifest_body).hexdigest()
    client.put(
        f"/v1/manifests/{manifest_digest}",
        content=manifest_body,
        headers=_json_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="PUT",
            path=f"/v1/manifests/{manifest_digest}",
            body=manifest_body,
            session_id=session_id,
        ),
    )
    commit_body = json.dumps(
        {"commit_id": "8fd99dd1-7a81-4c6f-b08b-659b176ad03f", "manifest_digest": manifest_digest, "manifest": manifest}
    ).encode("utf-8")
    commit_response = client.post(
        "/v1/commits",
        content=commit_body,
        headers=_json_headers(
            private_key,
            site_slug="test-site",
            key_fingerprint=key_fingerprint,
            method="POST",
            path="/v1/commits",
            body=commit_body,
            session_id=session_id,
        ),
    )
    assert commit_response.status_code == 409
