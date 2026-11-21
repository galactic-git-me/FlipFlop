import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_non_development_rejects_default_customer_jwt_secret(app_env):
    with pytest.raises(ValidationError, match="SECRET_KEY must be configured"):
        Settings(app_env=app_env, _env_file=None)


def test_non_development_accepts_configured_customer_jwt_secret():
    settings = Settings(app_env="production", secret_key="s" * 48, _env_file=None)

    assert settings.secret_key == "s" * 48


def test_development_keeps_development_jwt_secret_default():
    settings = Settings(app_env="dev", _env_file=None)

    assert settings.secret_key == "dev-secret-key-change-in-production"
