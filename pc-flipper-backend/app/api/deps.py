from fastapi import Header, HTTPException
from app.config import get_settings


def require_operator(x_admin_key: str | None = Header(default=None)) -> None:
    cfg = get_settings()
    # Backward compatible: if no key configured, keep local-dev access open.
    if not cfg.admin_api_key:
        return
    if not x_admin_key or x_admin_key != cfg.admin_api_key:
        raise HTTPException(status_code=403, detail="Operator key required")
