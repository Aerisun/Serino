#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def _derive_key(passphrase: str, *, salt: bytes) -> bytes:
    if len(passphrase) < 8:
        raise SystemExit("Passphrase must be at least 8 characters.")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def _decrypt_payload(payload: dict[str, str], passphrase: str) -> bytes:
    if payload.get("scheme") != "passphrase-aesgcm":
        raise SystemExit(f"Unsupported escrow scheme: {payload.get('scheme')}")
    key = _derive_key(passphrase, salt=base64.b64decode(payload["salt"]))
    return AESGCM(key).decrypt(
        base64.b64decode(payload["nonce"]),
        base64.b64decode(payload["ciphertext"]),
        None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and decrypt an Aerisun backup recovery key from sqlite.")
    parser.add_argument("--db", required=True, help="Path to aerisun.db")
    parser.add_argument("--credential-ref", default="aerisun-backup-source", help="Credential ref to export")
    parser.add_argument("--fingerprint", default=None, help="Optional specific fingerprint to export")
    parser.add_argument("--passphrase", required=True, help="Passphrase used when the key escrow was exported")
    parser.add_argument("--out", default=None, help="Optional output PEM path")
    args = parser.parse_args()

    connection = sqlite3.connect(Path(args.db).expanduser().resolve())
    connection.row_factory = sqlite3.Row
    try:
        if args.fingerprint:
            row = connection.execute(
                """
                SELECT * FROM backup_recovery_keys
                WHERE credential_ref = ? AND secrets_fingerprint = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (args.credential_ref, args.fingerprint),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT * FROM backup_recovery_keys
                WHERE credential_ref = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (args.credential_ref,),
            ).fetchone()
        if row is None:
            raise SystemExit("Recovery key not found in database.")
        payload = json.loads(row["encrypted_private_payload"] or "{}")
        private_pem = _decrypt_payload(payload, args.passphrase)
    finally:
        connection.close()

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(private_pem)
        print(out_path)
        return

    print(private_pem.decode("utf-8"))


if __name__ == "__main__":
    main()
