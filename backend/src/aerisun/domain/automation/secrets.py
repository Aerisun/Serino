"""Small AES-GCM envelope for automation secrets stored in the local single-node deployment."""

from __future__ import annotations

import base64
import os
from collections.abc import Mapping, Sequence
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aerisun.core.redaction import SECRET_ENVELOPE_PREFIX, is_sensitive_key
from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import StateConflict

_KEY_FILENAME = "automation-master-key-v1"
_NONCE_BYTES = 12


def _master_key_path():
    return get_settings().secrets_dir / _KEY_FILENAME


def _load_or_create_master_key() -> bytes:
    path = _master_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        key = path.read_bytes()
    except FileNotFoundError:
        generated = AESGCM.generate_key(bit_length=256)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            key = path.read_bytes()
        else:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(generated)
            key = generated
    try:
        path.chmod(0o600)
    except OSError as exc:
        raise StateConflict("Automation secret key permissions could not be secured") from exc
    if len(key) != 32:
        raise StateConflict("Automation secret key is invalid")
    return key


def is_encrypted_secret(value: object) -> bool:
    return isinstance(value, str) and value.startswith(SECRET_ENVELOPE_PREFIX)


def encrypt_secret(value: str | None, *, purpose: str) -> str:
    plaintext = str(value or "")
    if not plaintext or is_encrypted_secret(plaintext):
        return plaintext
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_load_or_create_master_key()).encrypt(
        nonce,
        plaintext.encode("utf-8"),
        purpose.encode("utf-8"),
    )
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{SECRET_ENVELOPE_PREFIX}{encoded}"


def decrypt_secret(value: str | None, *, purpose: str) -> str:
    encoded_value = str(value or "")
    if not encoded_value or not is_encrypted_secret(encoded_value):
        return encoded_value
    token = encoded_value.removeprefix(SECRET_ENVELOPE_PREFIX)
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        plaintext = AESGCM(_load_or_create_master_key()).decrypt(
            nonce,
            ciphertext,
            purpose.encode("utf-8"),
        )
    except Exception as exc:
        raise StateConflict("Automation secret could not be decrypted") from exc
    return plaintext.decode("utf-8")


def protect_sensitive_data(value: Any, *, purpose: str) -> Any:
    if isinstance(value, Mapping):
        protected: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if is_sensitive_key(text_key) and isinstance(item, str):
                protected[text_key] = encrypt_secret(item, purpose=purpose)
            else:
                protected[text_key] = protect_sensitive_data(item, purpose=purpose)
        return protected
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [protect_sensitive_data(item, purpose=purpose) for item in value]
    return value


def reveal_sensitive_data(value: Any, *, purpose: str) -> Any:
    if is_encrypted_secret(value):
        return decrypt_secret(value, purpose=purpose)
    if isinstance(value, Mapping):
        return {str(key): reveal_sensitive_data(item, purpose=purpose) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [reveal_sensitive_data(item, purpose=purpose) for item in value]
    return value
