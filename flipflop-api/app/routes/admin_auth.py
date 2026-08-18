import structlog
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.admin_auth import AdminLoginRequest, AdminTokenResponse, AdminUserResponse
from app.services.admin_auth_service import admin_login, get_admin_by_token
from app.models.admin_user import AdminUser

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


async def get_current_admin(
    request: Request,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Resolve the admin identity.

    The admin UI is a personal tool running on this PC, so loopback requests
    do not require a login. Requests arriving from any other machine still
    require a valid admin JWT; binding the dev server to 0.0.0.0 must not turn
    into an unauthenticated LAN-facing administration API.
    """
    client_host = request.client.host if request.client else None
    if client_host in {"127.0.0.1", "::1", "localhost"}:
        result = await db.execute(
            select(AdminUser).where(AdminUser.is_active.is_(True)).order_by(AdminUser.id)
        )
        admin = result.scalars().first()
        if not admin:
            raise HTTPException(status_code=503, detail="No active admin account is configured")
        return admin

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    admin = await get_admin_by_token(db, parts[1])
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")

    return admin


@router.post("/login", response_model=AdminTokenResponse)
async def admin_login_endpoint(
    request: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AdminTokenResponse:
    admin, access_token = await admin_login(db=db, email=request.email, password=request.password)

    if not admin:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AdminTokenResponse(access_token=access_token)


@router.get("/me", response_model=AdminUserResponse)
async def get_current_admin_endpoint(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUserResponse:
    return AdminUserResponse.model_validate(admin)
