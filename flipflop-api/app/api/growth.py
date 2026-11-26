"""HTTP boundary for the Growth Engine Marketing MVP."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.growth import ApprovalRequest, GrowthAuditEvent, GrowthDispatchControl, SocialAccount, SocialPost, TrackingLink
from app.models.admin_user import AdminUser
from app.routes.admin_auth import get_current_admin
from app.services import growth_social as social
from app.services.growth_release import FeatureNotEnabled, get_active_release, serialize_release

router = APIRouter(prefix="/growth", tags=["growth"])


def _error(error: Exception) -> HTTPException:
    if isinstance(error, FeatureNotEnabled):
        return HTTPException(409, {"code": error.code, "capability": error.capability})
    if isinstance(error, PermissionError):
        return HTTPException(403, str(error))
    return HTTPException(422, str(error))


async def _serialize_post(db: AsyncSession, post: SocialPost) -> dict:
    """Attach the immutable current revision without leaking ORM objects."""
    return social.serialize_post(post, await social.latest_revision(db, post.id))


@router.get("/release", dependencies=[Depends(get_current_admin)])
async def release(db: AsyncSession = Depends(get_db)):
    return serialize_release(await get_active_release(db))


@router.get("/command-centre", dependencies=[Depends(get_current_admin)])
async def command_centre(db: AsyncSession = Depends(get_db)):
    return await social.command_centre(db)


@router.get("/social/accounts", dependencies=[Depends(get_current_admin)])
async def accounts(db: AsyncSession = Depends(get_db)):
    await social.ensure_seed(db)
    return {"items": await social.list_accounts(db)}


@router.get("/assets", dependencies=[Depends(get_current_admin)])
async def assets(db: AsyncSession = Depends(get_db)):
    await social.ensure_seed(db)
    return {"items": await social.list_assets(db)}


@router.get("/social/posts", dependencies=[Depends(get_current_admin)])
async def posts(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SocialPost).order_by(SocialPost.updated_at.desc()))).scalars().all()
    return {"items": [await _serialize_post(db, row) for row in rows]}


@router.post("/social/posts", status_code=201, dependencies=[Depends(get_current_admin)])
async def create_post(payload: dict[str, Any], admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    try:
        post = await social.create_post(db, payload, actor=admin.email)
        return await _serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.patch("/social/posts/{post_id}", dependencies=[Depends(get_current_admin)])
async def revise_post(post_id: int, payload: dict[str, Any], admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.revise_post(db, post, payload, actor=admin.email)
        return await _serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/social/posts/{post_id}/submit", dependencies=[Depends(get_current_admin)])
async def submit_post(post_id: int, payload: dict[str, Any] | None = None, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.submit_for_review(db, post, actor=admin.email)
        return await _serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/social/posts/{post_id}/approval", dependencies=[Depends(get_current_admin)])
async def decide_post(post_id: int, payload: dict[str, Any], admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.decide_approval(db, post, approve=bool(payload.get("approve")), actor=admin.email, reason=str(payload.get("reason") or ""))
        return await _serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/social/posts/{post_id}/execute", dependencies=[Depends(get_current_admin)])
async def execute_post(post_id: int, payload: dict[str, Any] | None = None, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.schedule_or_publish(db, post, actor=admin.email)
        return await _serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/approvals", dependencies=[Depends(get_current_admin)])
async def approvals(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()))).scalars().all()
    return {"items": [{"id": row.id, "subject_type": row.subject_type, "subject_id": row.subject_id, "action": row.action, "status": row.status, "requested_by": row.requested_by, "decided_by": row.decided_by, "reason": row.reason, "expires_at": row.expires_at.isoformat() if row.expires_at else None} for row in rows]}


@router.get("/audit", dependencies=[Depends(get_current_admin)])
async def audit(limit: int = 100, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(GrowthAuditEvent).order_by(GrowthAuditEvent.created_at.desc()).limit(min(max(limit, 1), 500)))).scalars().all()
    return {"items": [{"id": row.id, "actor": row.actor, "action": row.action, "subject_type": row.subject_type, "subject_id": row.subject_id, "detail": row.detail, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]}


@router.post("/analytics/events", status_code=202)
async def ingest_event(payload: dict[str, Any], db: AsyncSession = Depends(get_db)):
    try:
        event = await social.ingest_website_event(db, payload)
        return {"id": event.id, "status": "accepted"}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/analytics", dependencies=[Depends(get_current_admin)])
async def analytics(db: AsyncSession = Depends(get_db)):
    return await social.analytics_summary(db)


@router.post("/dispatch-control", dependencies=[Depends(get_current_admin)])
async def update_dispatch_control(payload: dict[str, Any], admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    paused = payload.get("is_paused")
    if not isinstance(paused, bool):
        raise HTTPException(422, "is_paused must be a boolean")
    control = await social.set_dispatch_pause(
        db,
        paused=paused,
        actor=admin.email,
        reason=str(payload.get("reason") or ""),
    )
    return _serialize_dispatch_control(control)


@router.patch("/social/accounts/{account_id}", dependencies=[Depends(get_current_admin)])
async def disable_social_account(account_id: int, payload: dict[str, Any], admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    account = await db.get(SocialAccount, account_id)
    if account is None:
        raise HTTPException(404, "Social account not found")
    enabled = payload.get("enabled")
    if enabled is not False:
        raise HTTPException(409, "A provider connection must be established before an account can be enabled")
    account.status = "disabled"
    account.health = "disabled"
    account.health_detail = "Disabled by administrator"
    await social.audit(db, "account.disabled", admin.email, "social_account", account.id)
    return social.serialize_account(account)


def _serialize_dispatch_control(control: GrowthDispatchControl) -> dict:
    return {
        "is_paused": control.is_paused,
        "reason": control.reason,
        "updated_by": control.updated_by,
        "updated_at": control.updated_at.isoformat() if control.updated_at else None,
    }


@router.get("/track/{slug}")
async def follow_tracking_link(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    link = (await db.execute(select(TrackingLink).where(TrackingLink.slug == slug))).scalar_one_or_none()
    if not link:
        raise HTTPException(404, "Tracking link not found")
    link.click_count += 1
    await social.ingest_website_event(db, {"event_name": "tracked_link_click", "session_id": request.headers.get("x-session-id", ""), "path": request.url.path, "utm": {"utm_source": link.utm_source, "utm_medium": link.utm_medium, "utm_campaign": link.utm_campaign, "utm_content": link.utm_content}})
    return RedirectResponse(social.tracked_url(link), status_code=307)
