#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aerisun.core.settings import get_settings  # noqa: E402


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_bytes(path: Path, payload: bytes, *, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Aerisun backup-sync recovery keys for encrypted backups."
    )
    parser.add_argument(
        "--credential-ref",
        default="aerisun-backup-source",
        help="Credential directory name under <secrets_dir>/backup-sync/.",
    )
    parser.add_argument(
        "--site-slug",
        default=None,
        help="Site slug label printed in the output. Defaults to AERISUN_BACKUP_SYNC_DEFAULT_SITE_SLUG.",
    )
    parser.add_argument(
        "--secrets-dir",
        default=None,
        help="Override the Aerisun secrets directory. Defaults to AERISUN_SECRETS_DIR / .store/secrets.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing credential files if they already exist.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    settings = get_settings()
    site_slug = (args.site_slug or settings.backup_sync_default_site_slug).strip() or "aerisun"
    secrets_dir = Path(args.secrets_dir).expanduser().resolve() if args.secrets_dir else settings.secrets_dir
    credential_dir = secrets_dir / "backup-sync" / args.credential_ref

    secrets_private = x25519.X25519PrivateKey.generate()
    secrets_public = secrets_private.public_key()

    secrets_private_pem = secrets_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    secrets_public_pem = secrets_public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    secrets_fingerprint = _sha256_hex(
        secrets_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )

    _write_bytes(credential_dir / "secrets_x25519.pem", secrets_private_pem, force=args.force)
    _write_bytes(credential_dir / "secrets_x25519.pub.pem", secrets_public_pem, force=args.force)

    print("Backup recovery keys generated.")
    print(f"credential_ref: {args.credential_ref}")
    print(f"site_slug: {site_slug}")
    print(f"credential_dir: {credential_dir}")
    print(f"secrets_fingerprint: {secrets_fingerprint}")
    print()
    print("Keep this directory outside your runtime backup target.")
    print("It is required later to decrypt encrypted backup payloads.")


if __name__ == "__main__":
    main()
