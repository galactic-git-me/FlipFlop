from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from jose import jwt

from app.services import auth_service, ebay_oauth, license_key_crypto, portal_access
from app.services.rotating_secret import decode_application_token


def settings(current: str, previous: str = ""):
    return SimpleNamespace(
        secret_key=current,
        secret_key_previous=previous,
        jwt_algorithm="HS256",
        jwt_expiration_hours=168,
        app_env="test",
        ebay_token_encryption_key="",
        ebay_client_secret="",
    )


def test_rotating_secret_verifies_previous_and_signs_current(monkeypatch):
    old = "previous-secret-value-that-was-used-before"
    current = "current-secret-value-that-is-now-active"
    config = settings(current, old)
    old_token = jwt.encode({"sub": "42"}, old, algorithm="HS256")

    assert decode_application_token(old_token, config)["sub"] == "42"
    monkeypatch.setattr(auth_service, "settings", config)
    new_token = auth_service.create_access_token(42)
    assert jwt.decode(new_token, current, algorithms=["HS256"])["sub"] == "42"
    assert auth_service.verify_token(old_token) == 42


def test_guest_portal_capability_accepts_previous_key(monkeypatch):
    old = "previous-secret-value-that-was-used-before"
    config = settings("current-secret-value-that-is-now-active", old)
    token = jwt.encode({
        "typ": "guest_portal",
        "scope": "portal:read",
        "capabilities": ["support:create"],
    }, old, algorithm="HS256")
    monkeypatch.setattr(portal_access, "get_settings", lambda: config)

    assert portal_access.guest_portal_token_has_capability(token, "support:create")
    assert not portal_access.guest_portal_token_has_capability(token, "order:write")


def test_license_cipher_decrypts_previous_and_encrypts_current(monkeypatch):
    old = "previous-secret-value-that-was-used-before"
    current = "current-secret-value-that-is-now-active"
    monkeypatch.setattr(license_key_crypto, "get_settings", lambda: settings(old))
    old_encrypted = license_key_crypto.encrypt_license_key("WIN-LICENSE-CODE")
    monkeypatch.setattr(license_key_crypto, "get_settings", lambda: settings(current, old))

    assert license_key_crypto.decrypt_license_key(old_encrypted) == "WIN-LICENSE-CODE"
    new_encrypted = license_key_crypto.encrypt_license_key("NEW-LICENSE-CODE")
    monkeypatch.setattr(license_key_crypto, "get_settings", lambda: settings(current))
    assert license_key_crypto.decrypt_license_key(new_encrypted) == "NEW-LICENSE-CODE"


def test_ebay_cipher_decrypts_previous_secret(monkeypatch):
    old = "previous-secret-value-that-was-used-before"
    current = "current-secret-value-that-is-now-active"
    monkeypatch.setattr(ebay_oauth, "get_settings", lambda: settings(old))
    old_encrypted = ebay_oauth._encrypt_token("ebay-refresh-token")
    monkeypatch.setattr(ebay_oauth, "get_settings", lambda: settings(current, old))

    assert ebay_oauth._decrypt_token(old_encrypted) == ("ebay-refresh-token", False)
    new_encrypted = ebay_oauth._encrypt_token("new-ebay-refresh-token")
    assert ebay_oauth._decrypt_token(new_encrypted) == ("new-ebay-refresh-token", False)


def test_production_rotation_is_atomic_and_idempotent(tmp_path):
    script_path = Path(__file__).resolve().parents[3] / "deploy" / "rotate-production-secret-key.py"
    spec = importlib.util.spec_from_file_location("rotate_production_secret_key", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    env_file = tmp_path / ".env.local"
    env_file.write_text("APP_ENV=production\nSECRET_KEY=short-old-key\n", encoding="utf-8")
    result = module.rotate(env_file)
    contents = env_file.read_text(encoding="utf-8")
    assert "rotated atomically" in result
    assert "SECRET_KEY_PREVIOUS=short-old-key" in contents
    new_value = next(line.split("=", 1)[1] for line in contents.splitlines() if line.startswith("SECRET_KEY="))
    assert len(new_value) >= 32
    assert "short-old-key" not in result
    assert "no rotation needed" in module.rotate(env_file)

