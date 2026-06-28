"""
Manual listing submission API.

POST /manual-submit/url      — submit a URL (eBay, Gumtree, Preloved, generic)
POST /manual-submit/image    — submit a photo (multipart/form-data)

Both endpoints run the full pipeline:
  scrape / analyse → parse_specs → resale_range → classify → save to DB

Returns the saved Listing (same schema as /listings/{id}).
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.listing import Listing, ListingStatus
from app.schemas.listing import ListingOut
from app.services.manual_scraper import scrape_url, analyse_image
from app.services.spec_parser import parse_specs
from app.services.classifier import score_listing
from app.services.estimator import estimate_upgrade_cost, estimate_profit
from app.services.resale_scraper import get_resale_range
from app.services.claude_eval_queue import enqueue_for_claude, should_queue_for_claude

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/manual-submit", tags=["manual-submit"])

# Accepted image MIME types
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB


class UrlSubmitRequest(BaseModel):
    url: str
    price_override: Optional[float] = None


# ─── URL submission ───────────────────────────────────────────────────────────

@router.post("/url", response_model=ListingOut)
async def submit_url(body: UrlSubmitRequest, db: AsyncSession = Depends(get_db)):
    """
    Fetch a listing URL, run it through the full pipeline, and save it to the DB.
    Accepts eBay, Gumtree, Preloved, and generic URLs.
    """
    url = body.url.strip()
    if not url.startswith("http"):
        raise HTTPException(422, "URL must start with http:// or https://")

    log.info("manual_submit.url.start", url=url[:80])

    try:
        raw = await scrape_url(url, price_override=body.price_override)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        log.warning("manual_submit.url.scrape_failed", url=url[:80], error=str(e))
        raise HTTPException(502, f"Could not fetch the page: {e}")

    listing = await _run_pipeline(raw, db)
    log.info("manual_submit.url.done", listing_id=listing.id, title=listing.title[:40])
    return listing


# ─── Image submission ─────────────────────────────────────────────────────────

@router.post("/image", response_model=ListingOut)
async def submit_image(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse a photo of a PC/component using the local Ollama vision model.
    Optionally supply title and price to override AI extraction.
    """
    # Validate
    content_type = file.content_type or "image/jpeg"
    if content_type not in _IMAGE_TYPES:
        raise HTTPException(415, f"Unsupported image type: {content_type}. Use JPEG, PNG or WebP.")

    image_bytes = await file.read()
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 15 MB)")
    if len(image_bytes) < 100:
        raise HTTPException(422, "Image file appears to be empty")

    log.info("manual_submit.image.start", size=len(image_bytes), content_type=content_type)

    try:
        raw = await analyse_image(
            image_bytes=image_bytes,
            content_type=content_type,
            user_title=title,
            user_price=price,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        log.warning("manual_submit.image.failed", error=str(e))
        raise HTTPException(502, f"Image analysis failed: {e}")

    listing = await _run_pipeline(raw, db)
    log.info("manual_submit.image.done", listing_id=listing.id, title=listing.title[:40])
    return listing


# ─── Shared pipeline ──────────────────────────────────────────────────────────

async def _run_pipeline(raw, db: AsyncSession) -> Listing:
    """
    Run a RawListing through the full evaluation pipeline and upsert into DB.
    Returns the saved Listing ORM object.
    """
    # Check for existing listing with same external_id (avoid duplicates on re-submit)
    existing = await db.execute(
        select(Listing).where(Listing.external_id == raw.external_id)
    )
    listing = existing.scalar_one_or_none()

    # Spec parsing
    specs = parse_specs(raw.title, raw.description)

    # Resale estimation
    resale_range = await get_resale_range(
        specs.cpu, specs.ram_gb, specs.ram_type,
        specs.storage_gb, specs.storage_type, specs.gpu,
        buy_price=raw.price,
    )
    _is_am5 = any(h in raw.title.lower() for h in ("am5", "b650", "x670", "a620"))
    upgrade_cost = estimate_upgrade_cost(specs.storage_gb, specs.gpu, specs.has_psu, specs.ram_gb, is_am5=_is_am5)
    resale      = resale_range.median
    profit      = estimate_profit(raw.price, resale,            upgrade_cost)
    profit_low  = estimate_profit(raw.price, resale_range.low,  upgrade_cost)
    profit_high = estimate_profit(raw.price, resale_range.high, upgrade_cost)

    # Scoring
    score_result = score_listing(
        title=raw.title, price=raw.price, estimated_profit=profit,
        cpu=specs.cpu, ram_gb=specs.ram_gb, ram_type=specs.ram_type,
        storage_gb=specs.storage_gb, gpu=specs.gpu, has_psu=specs.has_psu,
        location=raw.location,
        profit_low=profit_low, profit_high=profit_high,
    )

    if listing:
        # Re-evaluate an existing manual submission
        listing.price                 = raw.price
        listing.status                = ListingStatus.active
        listing.estimated_resale      = resale
        listing.resale_low            = resale_range.low
        listing.resale_high           = resale_range.high
        listing.resale_comp_count     = resale_range.count
        listing.estimated_upgrade_cost= upgrade_cost
        listing.estimated_profit      = profit
        listing.classification        = score_result.classification
        listing.gem_score             = score_result.score
        listing.gem_signals           = score_result.signals
        if raw.image_urls:
            listing.image_urls        = raw.image_urls
    else:
        # Find a source_id for "Manual Submission" — use 0 if none exists
        from app.models.source import DataSource
        src_result = await db.execute(
            select(DataSource).where(DataSource.name.in_(["Manual Submission", "Manual Photo"]))
        )
        src = src_result.scalars().first()
        source_id = src.id if src else 0

        listing = Listing(
            external_id    = raw.external_id,
            source_id      = source_id,
            source_name    = raw.source_name,
            title          = raw.title,
            description    = raw.description,
            price          = raw.price,
            url            = raw.url or "",
            image_urls     = raw.image_urls,
            location       = raw.location,
            condition      = raw.condition,
            cpu            = specs.cpu,
            ram_gb         = specs.ram_gb,
            ram_type       = specs.ram_type,
            storage_gb     = specs.storage_gb,
            storage_type   = specs.storage_type,
            gpu            = specs.gpu,
            has_psu        = specs.has_psu,
            gem_score      = score_result.score,
            classification = score_result.classification,
            gem_signals    = score_result.signals,
            estimated_resale       = resale,
            resale_low             = resale_range.low,
            resale_high            = resale_range.high,
            resale_comp_count      = resale_range.count,
            estimated_profit       = profit,
            estimated_upgrade_cost = upgrade_cost,
            initial_estimated_profit = profit,
            listing_type   = raw.listing_type,
            listing_ends_at= raw.listing_ends_at,
            seller_name    = raw.seller_name,
            seller_type    = raw.seller_type,
        )
        db.add(listing)

    await db.flush()
    needs_claude = listing.claude_judged_at is None and should_queue_for_claude(listing)
    listing_id = listing.id
    await db.refresh(listing)
    await db.commit()

    if needs_claude and listing_id:
        enqueue_for_claude(listing_id)

    return listing
