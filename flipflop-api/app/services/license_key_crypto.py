"""Encryption helpers for Windows licence keys stored in OSComponent rows."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


_PREFIX = "enc:v1:"


class LicenseKeyEncryptionError(RuntimeError):
    pass


def _cipher() -> Fernet:
    settings = get_settings()
    secret = settings.secret_key
    if not secret or (
        secret == "dev-secret-key-change-in-production"
        and settings.app_env.casefold() not in {"dev", "development", "test"}
    ):
        raise LicenseKeyEncryptionError("Configure a stable production SECRET_KEY before storing Windows licence keys")
    derived_key = base64.urlsafe_b64encode(
        hashlib.sha256(b"flipflop:os-component-license:v1:" + secret.encode("utf-8")).digest()
    )
    return Fernet(derived_key)


def encrypt_license_key(value: str | None) -> str | None:
    if value is None or not value:
        return value
    if value.startswith(_PREFIX):
        return value
    try:
        token = _cipher().encrypt(value.encode("utf-8")).decode("ascii")
    except (ValueError, TypeError) as error:
        raise LicenseKeyEncryptionError("Could not encrypt Windows licence key") from error
    return _PREFIX + token


def decrypt_license_key(value: str | None) -> str | None:
    if value is None or not value:
        return value
    if not value.startswith(_PREFIX):
        # Legacy plaintext rows remain readable until the encryption migration
        # is applied; new ORM writes are encrypted by EncryptedLicenseKey.
        return value
    try:
        return _cipher().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as error:
        raise LicenseKeyEncryptionError("Stored Windows licence key could not be decrypted") from error
