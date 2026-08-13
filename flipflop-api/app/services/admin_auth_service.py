import structlog
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.admin_user import AdminUser
from app.services.auth_service import hash_password, verify_password

log = structlog.get_logger(__name__)
settings = get_settings()

# Distinct token audience from customer auth (app/services/auth_service.py) so an
# admin token can never be replayed against a customer endpoint or vice versa —
# admin_auth's get_current_admin dependency checks this claim explicitly.
ADMIN_TOKEN_AUDIENCE = "flipflop-admin"


def create_admin_access_token(admin_id: int) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=12)  # shorter-lived than customer tokens

    payload = {
        "sub": str(admin_id),
        "aud": ADMIN_TOKEN_AUDIENCE,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    log.debug("admin_auth.token_created", admin_id=admin_id, expires_at=expires_at.isoformat())
    return token


def verify_admin_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=ADMIN_TOKEN_AUDIENCE,
        )
        admin_id_str = payload.get("sub")
        if admin_id_str is None:
            return None
        return int(admin_id_str)
    except JWTError as e:
        log.warning("admin_auth.token_verify_failed", error=str(e))
        return None


async def admin_login(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[AdminUser, str] | tuple[None, None]:
    result = await db.execute(select(AdminUser).where(AdminUser.email == email.lower()))
    admin = result.scalar_one_or_none()

    if not admin or not admin.is_active:
        log.warning("admin_auth.login_failed", reason="not_found_or_inactive", email=email)
        return None, None

    if not verify_password(password, admin.password_hash):
        log.warning("admin_auth.login_failed", reason="invalid_password", email=email)
        return None, None

    # admin_users.last_login/updated_at are naive DateTime columns (matches the
    # AdminUser model's datetime.utcnow() default) — a tz-aware value here trips
    # asyncpg ("can't subtract offset-naive and offset-aware datetimes").
    now_naive = datetime.utcnow()
    admin.last_login = now_naive
    admin.updated_at = now_naive
    db.add(admin)

    access_token = create_admin_access_token(admin.id)
    await db.commit()
    log.info("admin_auth.login_success", admin_id=admin.id, email=email)

    return admin, access_token


async def get_admin_by_token(db: AsyncSession, token: str) -> AdminUser | None:
    admin_id = verify_admin_token(token)
    if admin_id is None:
        return None

    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    admin = result.scalar_one_or_none()

    if not admin or not admin.is_active:
        return None

    return admin


__all__ = [
    "hash_password",
    "verify_password",
    "create_admin_access_token",
    "verify_admin_token",
    "admin_login",
    "get_admin_by_token",
]
