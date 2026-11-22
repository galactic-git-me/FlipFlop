"""Read application tokens signed before a controlled SECRET_KEY rotation."""
from __future__ import annotations

from jose import JWTError, jwt


def decode_application_token(token: str, settings) -> dict:
    """Decode with the current key, then the optional previous key.

    Signing always uses the current key. Algorithms and all normal jose claim
    validation remain enforced for either key.
    """
    secrets = [settings.secret_key]
    previous = getattr(settings, "secret_key_previous", "")
    if previous and previous not in secrets:
        secrets.append(previous)
    last_error: JWTError | None = None
    for secret in secrets:
        try:
            return jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
        except JWTError as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise JWTError("No application signing key is configured")
