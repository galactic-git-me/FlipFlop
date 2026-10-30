"""Operator queue API and separately authenticated desktop-worker API."""
from datetime import datetime, timedelta
import hmac
import os
import secrets
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_operator
from app.database import get_db
from app.models.browser_listing_job import BrowserListingJob
from app.models.channel_listing import ChannelListing
from app.models.manual_build import ManualBuild
from app.services.browser_listing_jobs import enqueue_browser_job, complete_browser_job, seller_pack

router = APIRouter(prefix="/cross-listing/browser-jobs", tags=["cross-listing"], dependencies=[Depends(require_operator)])


def require_worker(x_worker_key: str | None = Header(default=None)):
    expected = os.getenv("CROSS_LISTING_WORKER_KEY", "")
    if not expected or not x_worker_key or not hmac.compare_digest(expected, x_worker_key):
        raise HTTPException(403, "Browser worker authentication required")


worker_router = APIRouter(prefix="/cross-listing/browser-worker", tags=["cross-listing-worker"], dependencies=[Depends(require_worker)])


class QueueIn(BaseModel):
    build_id: int
    channel: str
    operation: Literal["publish", "relist"] = "publish"
    image_urls: list[str] = Field(default_factory=list, max_length=24)


class LeaseIn(BaseModel):
    lease_token: str = Field(min_length=32, max_length=64)


class ResultIn(LeaseIn):
    status: Literal["succeeded", "blocked", "needs_review", "observed"]
    message: str = Field(min_length=1, max_length=500)
    listing_url: str | None = Field(default=None, max_length=1000)
    external_id: str | None = Field(default=None, max_length=100)
    evidence: dict | None = None
    remote_state: Literal["active", "ended", "missing", "sold", "unknown"] | None = None
    order_id: str | None = Field(default=None, max_length=120)


def summary(job):
    return {"id": job.id, "channel_listing_id": job.channel_listing_id, "status": job.status,
        "operation": job.operation, "build_id": job.payload.get("build_id"), "channel": job.payload.get("channel"),
        "message": job.message, "updated_at": job.updated_at.isoformat() if job.updated_at else None}


@router.post("")
async def queue(body: QueueIn, db: AsyncSession = Depends(get_db)):
    try:
        from app.services.channel_images import prepare_channel_urls, cached_variant_url
        build = await db.get(ManualBuild, body.build_id)
        if not build:
            raise ValueError("Build not found")
        originals = [p["url"] for p in build.photos or [] if isinstance(p, dict) and p.get("kind", "photo") == "photo" and p.get("url")]
        # Client may choose only original photographs saved on this build.
        variants = {cached_variant_url(url, body.channel): url for url in originals}
        chosen = [url if url in originals else variants.get(url) for url in body.image_urls]
        if any(url is None for url in chosen):
            raise ValueError("Choose product photographs saved on this build")
        images = await prepare_channel_urls(chosen or originals, body.channel)
        job = await enqueue_browser_job(db, body.build_id, body.channel, operation=body.operation, image_urls=images)
        await db.commit()
        return summary(job)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("")
async def jobs(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(BrowserListingJob).order_by(BrowserListingJob.id.desc()).limit(100))).scalars().all()
    return [summary(row) for row in rows]


@router.get("/{job_id}/seller-pack")
async def pack(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(BrowserListingJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job.payload


@router.post("/{job_id}/retry")
async def retry(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(BrowserListingJob).where(BrowserListingJob.id == job_id).with_for_update())).scalar_one_or_none()
    if not job or job.status not in {"blocked", "needs_review"}:
        raise HTTPException(409, "Only a blocked or interrupted job can be resumed")
    # Resume must reconcile the seller account before any write; no blind retry.
    job.status, job.message, job.available_at = "queued", "Resuming: verify remote state before publishing.", datetime.utcnow()
    await db.commit()
    return summary(job)


async def leased(db, job_id, token):
    peek = await db.get(BrowserListingJob, job_id)
    if peek:
        await db.execute(select(ManualBuild).where(ManualBuild.id == peek.payload.get("build_id")).with_for_update())
    job = (await db.execute(select(BrowserListingJob).where(BrowserListingJob.id == job_id).with_for_update())).scalar_one_or_none()
    if not job or job.status != "running" or not secrets.compare_digest(job.lease_token or "", token) or not job.lease_until or job.lease_until < datetime.utcnow():
        raise HTTPException(409, "Job lease is no longer valid; reconcile before retrying")
    return job


@worker_router.post("/claim")
async def claim(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    expired = (await db.execute(select(BrowserListingJob).where(BrowserListingJob.status == "running",
        BrowserListingJob.lease_until < now).with_for_update(skip_locked=True))).scalars().all()
    for job in expired:
        await complete_browser_job(db, job, status="needs_review", message="Desktop worker stopped before confirming the outcome. Reconcile the vendor before resuming.")
    from app.services.browser_listing_jobs import BROWSER_CHANNELS
    job = (await db.execute(select(BrowserListingJob).where(BrowserListingJob.status == "queued",
        BrowserListingJob.available_at <= now, BrowserListingJob.payload["channel"].as_string().in_(BROWSER_CHANNELS))
        .order_by(case((BrowserListingJob.operation == "withdraw", 0), (BrowserListingJob.operation == "sale_check", 1), (BrowserListingJob.operation == "inspect", 3), else_=2), BrowserListingJob.id)
        .with_for_update(skip_locked=True).limit(1))).scalar_one_or_none()
    if not job:
        await db.commit()
        return None
    row = await db.get(ChannelListing, job.channel_listing_id)
    build = await db.get(ManualBuild, row.manual_build_id)
    try:
        from app.services.channel_sync import build_is_unavailable
        if job.operation not in {"inspect", "sale_check", "withdraw"} and await build_is_unavailable(db, build):
            raise ValueError("Build is sold or archived; no listing write is permitted")
        # Refresh saved copy/price but retain the reviewed image selection.
        job.payload = seller_pack(build, row, job.payload["listing"]["images"], operation=job.operation)
    except ValueError as exc:
        await complete_browser_job(db, job, status="blocked", message=str(exc))
        await db.commit()
        return None
    job.status, job.lease_token, job.lease_until = "running", secrets.token_hex(32), now + timedelta(minutes=5)
    await db.commit()
    return {**summary(job), "lease_token": job.lease_token, "payload": job.payload,
        "runtime": os.getenv("FLIPFLOP_RUNTIME_ENV", "development")}


@worker_router.post("/{job_id}/heartbeat")
async def heartbeat(job_id: int, body: LeaseIn, db: AsyncSession = Depends(get_db)):
    job = await leased(db, job_id, body.lease_token)
    job.lease_until = datetime.utcnow() + timedelta(minutes=5)
    await db.commit()
    return {"ok": True}


@worker_router.post("/{job_id}/preflight")
async def preflight(job_id: int, body: LeaseIn, db: AsyncSession = Depends(get_db)):
    job = await leased(db, job_id, body.lease_token)
    row = await db.get(ChannelListing, job.channel_listing_id)
    build = await db.get(ManualBuild, row.manual_build_id)
    try:
        from app.services.channel_sync import build_is_unavailable
        if job.operation not in {"inspect", "sale_check", "withdraw"} and await build_is_unavailable(db, build):
            raise ValueError("Build is sold or archived; no listing write is permitted")
        current = seller_pack(build, row, job.payload["listing"]["images"], operation=job.operation)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if current != job.payload:
        raise HTTPException(409, "Canonical listing changed during this job; restart with the saved data")
    return {"ok": True}


@worker_router.post("/{job_id}/result")
async def result(job_id: int, body: ResultIn, db: AsyncSession = Depends(get_db)):
    job = await leased(db, job_id, body.lease_token)
    try:
        if body.status == "observed":
            from app.services.channel_sync import confirm_browser_observation
            await confirm_browser_observation(db, job, state=body.remote_state, external_id=body.external_id,
                listing_url=body.listing_url, evidence=body.evidence, order_id=body.order_id)
        else:
            await complete_browser_job(db, job, status=body.status, message=body.message,
                listing_url=body.listing_url, external_id=body.external_id, evidence=body.evidence)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return summary(job)
