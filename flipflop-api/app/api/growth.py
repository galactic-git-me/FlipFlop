"""HTTP boundary for the Growth Engine Marketing MVP."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.growth import ApprovalRequest, GrowthAuditEvent, SocialPost, TrackingLink
from app.services import growth_social as social
from app.services.growth_release import FeatureNotEnabled, get_active_release, serialize_release

router = APIRouter(prefix="/growth", tags=["growth"])


def _error(error: Exception) -> HTTPException:
    if isinstance(error, FeatureNotEnabled):
        return HTTPException(409, {"code": error.code, "capability": error.capability})
    if isinstance(error, PermissionError):
        return HTTPException(403, str(error))
    return HTTPException(422, str(error))


@router.get("/release")
async def release(db: AsyncSession = Depends(get_db)):
    return serialize_release(await get_active_release(db))


@router.get("/command-centre")
async def command_centre(db: AsyncSession = Depends(get_db)):
    return await social.command_centre(db)


@router.get("/social/accounts")
async def accounts(db: AsyncSession = Depends(get_db)):
    await social.ensure_seed(db)
    return {"items": await social.list_accounts(db)}


@router.get("/assets")
async def assets(db: AsyncSession = Depends(get_db)):
    await social.ensure_seed(db)
    return {"items": await social.list_assets(db)}


@router.get("/social/posts")
async def posts(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SocialPost).order_by(SocialPost.updated_at.desc()))).scalars().all()
    return {"items": [await social.serialize_post(db, row) for row in rows]}


@router.post("/social/posts", status_code=201)
async def create_post(payload: dict[str, Any], db: AsyncSession = Depends(get_db)):
    try:
        post = await social.create_post(db, payload, actor=str(payload.get("actor") or "owner"))
        return await social.serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.patch("/social/posts/{post_id}")
async def revise_post(post_id: int, payload: dict[str, Any], db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.revise_post(db, post, payload, actor=str(payload.get("actor") or "owner"))
        return await social.serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/social/posts/{post_id}/submit")
async def submit_post(post_id: int, payload: dict[str, Any] | None = None, db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.submit_for_review(db, post, actor=str((payload or {}).get("actor") or "owner"))
        return await social.serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/social/posts/{post_id}/approval")
async def decide_post(post_id: int, payload: dict[str, Any], db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.decide_approval(db, post, approve=bool(payload.get("approve")), actor=str(payload.get("actor") or "owner"), reason=str(payload.get("reason") or ""))
        return await social.serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/social/posts/{post_id}/execute")
async def execute_post(post_id: int, payload: dict[str, Any] | None = None, db: AsyncSession = Depends(get_db)):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(404, "Social post not found")
    try:
        post = await social.schedule_or_publish(db, post, actor=str((payload or {}).get("actor") or "owner"))
        return await social.serialize_post(db, post)
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/approvals")
async def approvals(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()))).scalars().all()
    return {"items": [{"id": row.id, "subject_type": row.subject_type, "subject_id": row.subject_id, "action": row.action, "status": row.status, "requested_by": row.requested_by, "decided_by": row.decided_by, "reason": row.reason, "expires_at": row.expires_at.isoformat() if row.expires_at else None} for row in rows]}


@router.get("/audit")
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


@router.get("/analytics")
async def analytics(db: AsyncSession = Depends(get_db)):
    return await social.analytics_summary(db)


@router.get("/track/{slug}")
async def follow_tracking_link(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    link = (await db.execute(select(TrackingLink).where(TrackingLink.slug == slug))).scalar_one_or_none()
    if not link:
        raise HTTPException(404, "Tracking link not found")
    link.click_count += 1
    await social.ingest_website_event(db, {"event_name": "tracked_link_click", "session_id": request.headers.get("x-session-id", ""), "path": request.url.path, "utm": {"utm_source": link.utm_source, "utm_medium": link.utm_medium, "utm_campaign": link.utm_campaign, "utm_content": link.utm_content}})
    return RedirectResponse(social.tracked_url(link), status_code=307)
