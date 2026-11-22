from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from jose import JWTError, jwt

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
    env_file.write_text("SECRET_KEY=short-old-key\nAPP_ENV=production", encoding="utf-8")
    result = module.rotate(env_file)
    contents = env_file.read_text(encoding="utf-8")
    assert "rotated atomically" in result
    assert "SECRET_KEY_PREVIOUS=short-old-key" in contents
    assert "APP_ENV=production\nSECRET_KEY_PREVIOUS=short-old-key" in contents
    new_value = next(line.split("=", 1)[1] for line in contents.splitlines() if line.startswith("SECRET_KEY="))
    assert len(new_value) >= 32
    assert "short-old-key" not in result
    assert "no rotation needed" in module.rotate(env_file)


def test_production_rotation_bootstraps_missing_key_without_trusting_builtin_fallback(tmp_path):
    script_path = Path(__file__).resolve().parents[3] / "deploy" / "rotate-production-secret-key.py"
    spec = importlib.util.spec_from_file_location("rotate_production_secret_key_missing", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    env_file = tmp_path / ".env.local"
    env_file.write_text("APP_ENV=production\n", encoding="utf-8")
    result = module.rotate(env_file)
    contents = env_file.read_text(encoding="utf-8")
    keys = dict(line.split("=", 1) for line in contents.splitlines() if "=" in line)

    assert "Missing production key replaced safely" in result
    assert len(keys["SECRET_KEY"]) >= 32
    assert "SECRET_KEY_PREVIOUS" not in keys
    assert "dev-secret-key-change-in-production" not in contents
    assert "no rotation needed" in module.rotate(env_file)


def test_production_rotation_recognizes_indented_existing_secret(tmp_path):
    script_path = Path(__file__).resolve().parents[3] / "deploy" / "rotate-production-secret-key.py"
    spec = importlib.util.spec_from_file_location("rotate_production_secret_key_indented", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    existing = "existing-production-key-that-is-long-enough-for-validation"
    env_file = tmp_path / ".env.local"
    original = f"APP_ENV=production\n  SECRET_KEY={existing}\n"
    env_file.write_text(original, encoding="utf-8")

    assert "already meets" in module.rotate(env_file)
    assert env_file.read_text(encoding="utf-8") == original


def test_production_rotation_rejects_malformed_key_assignment(tmp_path):
    script_path = Path(__file__).resolve().parents[3] / "deploy" / "rotate-production-secret-key.py"
    spec = importlib.util.spec_from_file_location("rotate_production_secret_key_malformed", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    env_file = tmp_path / ".env.local"
    original = "APP_ENV=production\n SECRET_KEY : existing-key\n"
    env_file.write_text(original, encoding="utf-8")

    try:
        module.rotate(env_file)
    except ValueError as error:
        assert "unsupported syntax" in str(error)
    else:
        raise AssertionError("ambiguous secret assignment must be rejected")
    assert env_file.read_text(encoding="utf-8") == original


def test_bootstrapped_key_does_not_accept_tokens_signed_with_public_fallback(tmp_path):
    script_path = Path(__file__).resolve().parents[3] / "deploy" / "rotate-production-secret-key.py"
    spec = importlib.util.spec_from_file_location("rotate_production_secret_key_token", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    env_file = tmp_path / ".env.local"
    env_file.write_text("APP_ENV=production\n", encoding="utf-8")
    module.rotate(env_file)
    new_key = next(line.split("=", 1)[1] for line in env_file.read_text(encoding="utf-8").splitlines()
                   if line.startswith("SECRET_KEY="))
    legacy_token = jwt.encode({"sub": "42"}, "dev-secret-key-change-in-production", algorithm="HS256")

    try:
        decode_application_token(legacy_token, settings(new_key))
    except JWTError:
        pass
    else:
        raise AssertionError("public fallback token must not remain valid after bootstrap")


def test_production_rotation_rejects_previous_key_without_current_key(tmp_path):
    script_path = Path(__file__).resolve().parents[3] / "deploy" / "rotate-production-secret-key.py"
    spec = importlib.util.spec_from_file_location("rotate_production_secret_key_orphan_previous", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    env_file = tmp_path / ".env.local"
    original = "APP_ENV=production\nSECRET_KEY_PREVIOUS=old-value\n"
    env_file.write_text(original, encoding="utf-8")

    try:
        module.rotate(env_file)
    except ValueError as error:
        assert "previous key exists without a current key" in str(error)
    else:
        raise AssertionError("orphan previous key must require manual review")
    assert env_file.read_text(encoding="utf-8") == original

