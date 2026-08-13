import uuid
from datetime import datetime, date
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.flip import Flip, FlipStage
from app.models.listing import Listing, ListingStatus, Classification
from app.models.part import Part
from app.models.flip_intelligence import FlipIntelligence
from app.models.pricing_bias import PricingBias
from app.schemas.flip import FlipOut, FlipCreate, FlipUpdate
from app.services.selling_toolkit import generate_titles, generate_description
from app.services import ai_service
from app.services.alerts import emit_alert
from app.services import demand_check as demand_check_service
from app.services import pricing_engine
from app.services import offer_engine
from app.services.cpu_tier import extract_cpu_tier
from app.config import get_settings
import structlog

settings = get_settings()
router = APIRouter(prefix="/flips", tags=["flips"])
log = structlog.get_logger(__name__)


@router.get("/", response_model=list[FlipOut])
@router.get("", response_model=list[FlipOut], include_in_schema=False)
async def get_flips(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Flip).options(selectinload(Flip.listing)).order_by(Flip.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=FlipOut, status_code=201)
async def create_flip(body: FlipCreate, db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, body.listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    # Enforce concurrent flips limit
    active_result = await db.execute(
        select(Flip).where(Flip.stage.not_in([FlipStage.sold]))
    )
    active_count = len(active_result.scalars().all())
    if active_count >= settings.max_concurrent_flips:
        raise HTTPException(
            409,
            f"Max concurrent flips reached ({settings.max_concurrent_flips}). "
            "Increase the limit in Settings or sell an existing flip first."
        )

    flip = Flip(
        listing_id=body.listing_id,
        notes=body.notes,
        base_cost=listing.price,
        total_cost=listing.price,
        initial_estimated_resale=listing.estimated_resale,
        current_estimated_resale=listing.estimated_resale,
        initial_estimated_profit=listing.estimated_profit,
        current_estimated_profit=listing.estimated_profit,
    )
    db.add(flip)
    await db.flush()

    # Row 10/33: demand check fires automatically on build creation, no click needed.
    try:
        signal = await demand_check_service.check_demand(listing.cpu, listing.gpu)
        flip.demand_sold_count_90d = signal.sold_count_90d
        flip.demand_active_count = signal.active_count
        flip.demand_checked_at = signal.checked_at
    except Exception as exc:
        log.warning("flips.demand_check.failed", flip_id=flip.id, error=str(exc))

    # Rows 19/20: initial pricing anchor/floor computed alongside demand, so
    # margin and demand are judged together before parts are committed.
    try:
        await pricing_engine.recalculate_pricing(flip, db)
    except Exception as exc:
        log.warning("flips.pricing_recalc.failed", flip_id=flip.id, error=str(exc))

    await db.commit()
    result = await db.execute(
        select(Flip).where(Flip.id == flip.id).options(selectinload(Flip.listing))
    )
    return result.scalar_one()


@router.get("/{flip_id}", response_model=FlipOut)
async def get_flip(flip_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Flip).where(Flip.id == flip_id).options(selectinload(Flip.listing))
    )
    flip = result.scalar_one_or_none()
    if not flip:
        raise HTTPException(404, "Flip not found")
    return flip


@router.patch("/{flip_id}", response_model=FlipOut)
async def update_flip(flip_id: int, body: FlipUpdate, db: AsyncSession = Depends(get_db)):
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")

    if body.stage:
        flip.stage = body.stage
        if body.stage == FlipStage.sold:
            flip.sold_at = datetime.utcnow()

    if body.notes is not None:
        flip.notes = body.notes

    if body.actual_sale_price is not None:
        flip.actual_sale_price = body.actual_sale_price
        flip.actual_profit = body.actual_sale_price - flip.total_cost - (body.actual_sale_price * flip.platform_fee_pct)

    if body.sale_platform is not None:
        flip.sale_platform = body.sale_platform

    if body.selected_upgrade_ids is not None:
        flip.selected_upgrade_ids = body.selected_upgrade_ids
        await _recalculate_costs(flip, db)

    if body.min_offer_price is not None:
        flip.min_offer_price = body.min_offer_price
    if body.offers_enabled is not None:
        flip.offers_enabled = body.offers_enabled
    if body.listing_price is not None:
        flip.listing_price = body.listing_price
    if body.deferred_publish_at is not None:
        flip.deferred_publish_at = body.deferred_publish_at
    if body.traffic_band is not None:
        flip.traffic_band = body.traffic_band
    if body.promoted_enabled is not None:
        flip.promoted_enabled = body.promoted_enabled
    if body.promoted_ad_rate_pct is not None:
        flip.promoted_ad_rate_pct = body.promoted_ad_rate_pct
    if body.markdown_event_opt_in is not None:
        flip.markdown_event_opt_in = body.markdown_event_opt_in
    if body.recreate_price_step_pct is not None:
        flip.recreate_price_step_pct = body.recreate_price_step_pct

    await db.flush()

    if flip.stage == FlipStage.sold and flip.actual_profit is not None:
        try:
            await emit_alert(
                code="flip_resale_detected",
                source="flips",
                severity="info",
                message=(
                    f"Resale detected: Flip #{flip.id} sold on {flip.sale_platform or 'unknown'} "
                    f"with profit £{float(flip.actual_profit):.2f}."
                ),
            )
        except Exception as exc:
            log.warning("flips.alert.emit_failed", code="flip_resale_detected", error=str(exc))

    # Response model includes `listing`, which is lazy-loaded — must be
    # eager-loaded before returning or Pydantic serialization crashes trying
    # to lazy-load outside an await context (MissingGreenlet).
    result = await db.execute(
        select(Flip).where(Flip.id == flip.id).options(selectinload(Flip.listing))
    )
    return result.scalar_one()


class SoldPayload(BaseModel):
    actual_sale_price: float
    sale_platform: str


@router.post("/{flip_id}/sold")
async def mark_sold(flip_id: int, body: SoldPayload, db: AsyncSession = Depends(get_db)):
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")

    listing = await db.get(Listing, flip.listing_id)
    sold_at = datetime.utcnow()

    flip.stage = FlipStage.sold
    flip.sold_at = sold_at
    flip.actual_sale_price = body.actual_sale_price
    flip.sale_platform = body.sale_platform
    flip.actual_profit = body.actual_sale_price - flip.total_cost - (body.actual_sale_price * flip.platform_fee_pct)
    if listing:
        listing.status = ListingStatus.sold
        listing.sold_at = sold_at
        listing.classification = Classification.already_flipped

    # Write intelligence record
    days = (sold_at - flip.created_at).days if flip.created_at else 0
    roi = (flip.actual_profit / flip.total_cost * 100) if flip.total_cost else 0
    cpu_tier = extract_cpu_tier(listing.cpu if listing else None)

    case_theme = await _derive_case_theme(flip, db)
    intel = FlipIntelligence(
        flip_id=flip.id,
        source_site=listing.source_name if listing else "unknown",
        buy_price=listing.price if listing else flip.base_cost,
        gem_score_at_buy=listing.gem_score if listing else 0,
        cpu_tier=cpu_tier,
        had_gpu=bool(listing.gpu) if listing else False,
        had_storage=bool(listing.storage_gb) if listing else False,
        ram_gb=listing.ram_gb if listing else None,
        case_theme=case_theme,
        upgrade_cost=flip.upgrade_cost,
        total_cost=flip.total_cost,
        sell_price=body.actual_sale_price,
        sell_platform=body.sale_platform,
        days_to_sell=days,
        profit=flip.actual_profit,
        roi_pct=roi,
    )
    db.add(intel)
    await db.flush()

    # Row 49: a fast/near-asking sale is an underpriced signal — bias the
    # *next* similar build's (same cpu_tier) initial pricing anchor up,
    # rather than resetting to the same starting point every cycle.
    try:
        signal = pricing_engine.bias_from_fast_sale(
            days_to_sell=days, sale_price=body.actual_sale_price, listing_price=flip.listing_price,
        )
        if signal.was_fast_or_near_asking and cpu_tier:
            bias_row = await db.get(PricingBias, cpu_tier)
            if not bias_row:
                bias_row = PricingBias(cpu_tier=cpu_tier)
                db.add(bias_row)
            bias_row.anchor_bias_pct = signal.suggested_anchor_bias_pct
            bias_row.triggered_by_flip_id = flip.id
            await db.flush()
    except Exception as exc:
        log.warning("flips.pricing_bias.update_failed", flip_id=flip.id, error=str(exc))

    try:
        await emit_alert(
            code="flip_resale_detected",
            source="flips",
            severity="info",
            message=(
                f"Resale detected: Flip #{flip.id} sold on {flip.sale_platform or 'unknown'} "
                f"with profit £{float(flip.actual_profit or 0.0):.2f}."
            ),
        )
    except Exception as exc:
        log.warning("flips.alert.emit_failed", code="flip_resale_detected", error=str(exc))

    return {
        "status": "sold",
        "actual_profit": flip.actual_profit,
        "roi_pct": roi,
        "message": f"Flip #{flip_id} marked sold. Intelligence record saved.",
    }


@router.get("/{flip_id}/purchase-plan")
async def get_purchase_plan(flip_id: int, db: AsyncSession = Depends(get_db)):
    """
    Returns every selected upgrade part with full details (name, specs, price,
    source URL) so the frontend can render a purchasable shopping checklist.
    Also includes the base listing URL so the user can buy the base PC too.
    """
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    listing = await db.get(Listing, flip.listing_id)

    items = []

    # Base PC is always first
    if listing:
        items.append({
            "category": "base_pc",
            "label": "Base PC",
            "name": listing.title,
            "specs": f"{listing.cpu or ''} · {listing.ram_gb or '?'}GB {listing.ram_type or ''} · {listing.gpu or 'No GPU'}".strip(" ·"),
            "price": listing.price,
            "url": listing.url,
            "source": listing.source_name,
            "part_id": None,
        })

    # Upgrades
    for category, part_id in (flip.selected_upgrade_ids or {}).items():
        try:
            part = await db.get(Part, int(part_id))
            if not part:
                continue
            price = part.price_used or part.price or 0.0
            items.append({
                "category": category,
                "label": category.replace("_", " ").title(),
                "name": part.name,
                "specs": part.specs or "",
                "price": price,
                "url": part.source_url or "",
                "source": part.source_site or "",
                "part_id": part.id,
            })
        except Exception:
            continue

    total = sum(i["price"] for i in items)
    return {"flip_id": flip_id, "items": items, "total": total}


@router.post("/{flip_id}/compatibility-check")
async def compatibility_check(flip_id: int, db: AsyncSession = Depends(get_db)):
    """
    Ask the local LLM to evaluate whether all selected upgrade components are
    compatible with the base PC specs.  Returns a structured verdict so the UI
    can gate progression from 'building' → 'ready_for_sale'.
    """
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    listing = await db.get(Listing, flip.listing_id)

    # Build base PC description
    base_lines = []
    if listing:
        if listing.cpu:        base_lines.append(f"CPU: {listing.cpu}")
        if listing.ram_gb:     base_lines.append(f"RAM: {listing.ram_gb}GB {listing.ram_type or ''}")
        if listing.storage_gb: base_lines.append(f"Storage: {listing.storage_gb}GB {listing.storage_type or ''}")
        if listing.gpu:        base_lines.append(f"GPU: {listing.gpu}")
        base_lines.append(f"Buy price: £{listing.price:.0f}")
    base_desc = "\n".join(base_lines) if base_lines else "Unknown base PC"

    # Collect selected upgrade parts
    upgrade_lines = []
    for category, part_id in (flip.selected_upgrade_ids or {}).items():
        try:
            part = await db.get(Part, int(part_id))
            if part:
                specs_note = f" ({part.specs})" if part.specs else ""
                upgrade_lines.append(f"- {category.upper()}: {part.name}{specs_note}")
        except Exception:
            continue

    upgrades_desc = "\n".join(upgrade_lines) if upgrade_lines else "No upgrades selected"

    prompt = f"""You are a PC hardware compatibility expert. Evaluate whether the selected upgrade components are compatible with the base PC.

BASE PC:
{base_desc}

SELECTED UPGRADES:
{upgrades_desc}

Check for these compatibility issues:
1. RAM type mismatch (e.g. DDR5 stick in a DDR4 board)
2. RAM speed/capacity exceeding motherboard limits
3. GPU power requirements vs PSU wattage
4. PCIe slot availability and version
5. CASE compatibility: form factor (ATX/mATX/ITX motherboard vs case support), maximum GPU length clearance vs selected GPU, CPU cooler height vs case max clearance, PSU form factor (ATX vs SFX)
6. CPU socket mismatch if a CPU upgrade is included
7. Storage interface mismatch (NVMe M.2 vs SATA)
8. PSU wattage adequacy: total system TDP (CPU + GPU + other components) must be comfortably below PSU rating

Respond in this EXACT JSON format (no markdown, no extra text):
{{
  "compatible": true or false,
  "confidence": "high" or "medium" or "low",
  "issues": ["list of specific incompatibility issues, empty if none"],
  "warnings": ["list of potential concerns that should be verified"],
  "summary": "one sentence summary"
}}"""

    try:
        response_text, model_used = await ai_service.chat(prompt, [])
        # Strip markdown code fences if present
        clean = response_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        import json
        result = json.loads(clean)
        result["model_used"] = model_used
        log.info("flips.compatibility_check", flip_id=flip_id, compatible=result.get("compatible"), model=model_used)
        return result
    except Exception as exc:
        log.warning("flips.compatibility_check.failed", flip_id=flip_id, error=str(exc))
        return {
            "compatible": None,
            "confidence": "low",
            "issues": [],
            "warnings": ["Compatibility check could not complete — AI backend may be offline."],
            "summary": "Unable to verify compatibility automatically.",
            "model_used": "none",
        }


@router.post("/{flip_id}/generate-listing")
async def generate_listing_content(flip_id: int, db: AsyncSession = Depends(get_db)):
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    listing = await db.get(Listing, flip.listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    titles, description = await ai_service.generate_listing_content(
        cpu=listing.cpu,
        ram_gb=listing.ram_gb,
        ram_type=listing.ram_type,
        storage_gb=listing.storage_gb,
        storage_type=listing.storage_type,
        gpu=listing.gpu,
        location=listing.location,
        case_theme=None,
    )
    if titles:
        flip.generated_title = titles[0]
    return {"titles": titles, "description": description}


class GenerateImagesBody(BaseModel):
    case_theme: str | None = None


@router.post("/{flip_id}/generate-images")
async def generate_images(
    flip_id: int,
    body: GenerateImagesBody = GenerateImagesBody(),
    db: AsyncSession = Depends(get_db),
):
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    listing = await db.get(Listing, flip.listing_id)

    images = await ai_service.generate_product_images(
        cpu=listing.cpu if listing else None,
        gpu=listing.gpu if listing else None,
        case_theme=body.case_theme,
        provider=settings.image_gen_provider,
        listing_images=listing.image_urls if listing else [],
    )
    return {"images": images, "reference_images": listing.image_urls if listing else []}


_VIDEO_TYPES = {"video/mp4", "video/quicktime"}
_MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100MB — eBay caps videos at 1 minute, this is generous headroom
_VIDEO_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads" / "videos"


@router.post("/{flip_id}/upload-video")
async def upload_video(
    flip_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Row 41: attach a boot-up/benchmark video. Saves locally immediately (so
    it's visible in the Photos tab right away) and, if a seller eBay OAuth
    token is connected, kicks off the eBay Media API push in the background
    — see ebay_media.py for the flagged "unverified schema" caveat.
    """
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")

    content_type = file.content_type or "video/mp4"
    if content_type not in _VIDEO_TYPES:
        raise HTTPException(415, f"Unsupported video type: {content_type}. Use MP4 or MOV.")

    video_bytes = await file.read()
    if len(video_bytes) > _MAX_VIDEO_BYTES:
        raise HTTPException(413, "Video too large (max 100MB)")
    if len(video_bytes) < 100:
        raise HTTPException(422, "Video file appears to be empty")

    _VIDEO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = "mp4" if content_type == "video/mp4" else "mov"
    filename = f"flip-{flip_id}-{uuid.uuid4().hex[:8]}.{ext}"
    (_VIDEO_UPLOAD_DIR / filename).write_bytes(video_bytes)

    flip.generated_video_url = f"/uploads/videos/{filename}"
    flip.video_ebay_status = "uploaded_local"
    await db.flush()

    background_tasks.add_task(_push_video_to_ebay_background, flip_id, video_bytes, content_type)

    return {"video_url": flip.generated_video_url, "video_ebay_status": flip.video_ebay_status}


async def _push_video_to_ebay_background(flip_id: int, video_bytes: bytes, content_type: str) -> None:
    from app.database import AsyncSessionLocal
    from app.services import ebay_oauth, ebay_media

    async with AsyncSessionLocal() as db:
        token = await ebay_oauth.get_valid_access_token(db)
        flip = await db.get(Flip, flip_id)
        if not flip:
            return
        if not token:
            log.info("flips.upload_video.ebay_push_skipped_no_token", flip_id=flip_id)
            return
        try:
            result = await ebay_media.upload_video_to_ebay(video_bytes, content_type, token)
            flip.video_ebay_status = "pushed_to_ebay" if result["success"] else "error"
        except Exception as exc:
            flip.video_ebay_status = "error"
            log.warning("flips.upload_video.ebay_push_failed", flip_id=flip_id, error=str(exc))
        await db.commit()


@router.post("/{flip_id}/demand-check")
async def rerun_demand_check(flip_id: int, db: AsyncSession = Depends(get_db)):
    """Row 10/33: re-run the sold-vs-active demand check on demand."""
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    listing = await db.get(Listing, flip.listing_id)
    signal = await demand_check_service.check_demand(listing.cpu if listing else None, listing.gpu if listing else None)
    flip.demand_sold_count_90d = signal.sold_count_90d
    flip.demand_active_count = signal.active_count
    flip.demand_checked_at = signal.checked_at
    await db.flush()
    return {
        "query": signal.query,
        "active_count": signal.active_count,
        "sold_count_90d": signal.sold_count_90d,
        "sold_data_available": signal.sold_data_available,
        "ratio_ok": signal.ratio_ok,
        "note": signal.note,
    }


@router.post("/{flip_id}/recalculate-pricing")
async def recalculate_pricing_endpoint(flip_id: int, db: AsyncSession = Depends(get_db)):
    """Rows 19/20/49: force a fresh sold-comp pricing recalculation."""
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    result = await pricing_engine.recalculate_pricing(flip, db)
    await db.flush()
    return result


class BuyerOfferBody(BaseModel):
    buyer_offer: float
    ebay_best_offer_id: str | None = None


@router.post("/{flip_id}/counter-offer")
async def counter_offer_endpoint(flip_id: int, body: BuyerOfferBody, db: AsyncSession = Depends(get_db)):
    """
    Rows 8/21: evaluate a buyer's Best Offer against the fixed two-round
    counter-offer rules, advance the flip's counter state, and — if
    ebay_best_offer_id is supplied and a seller token is available — post
    the decision back to eBay via the Trading API (RespondToBestOffer).
    Also called automatically by the offer_poll background job.
    """
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")

    listing_price = flip.listing_price or flip.current_estimated_resale or flip.total_cost
    result = offer_engine.evaluate_buyer_offer(
        buyer_offer=body.buyer_offer,
        listing_price=listing_price,
        min_offer_price=flip.min_offer_price,
        offers_enabled=flip.offers_enabled,
        counter_offer_round=flip.counter_offer_round,
        last_counter_offer_price=flip.last_counter_offer_price,
    )
    posted_to_ebay = False
    if result.action == "counter" and result.counter_price is not None:
        flip.last_counter_offer_price = result.counter_price
        flip.counter_offer_round += 1
        await db.flush()

        if body.ebay_best_offer_id and flip.ebay_listing_id:
            from app.services import ebay_oauth, ebay_trading_api
            token = await ebay_oauth.get_valid_access_token(db)
            if token:
                try:
                    await ebay_trading_api.respond_to_best_offer(
                        flip.ebay_listing_id, body.ebay_best_offer_id, "Counter", result.counter_price, token,
                    )
                    posted_to_ebay = True
                except Exception as exc:
                    log.warning("flips.counter_offer.ebay_post_failed", flip_id=flip.id, error=str(exc))

    return {
        "action": result.action,
        "counter_price": result.counter_price,
        "reason": result.reason,
        "posted_to_ebay": posted_to_ebay,
    }


@router.post("/{flip_id}/publish-now")
async def publish_now_endpoint(flip_id: int, db: AsyncSession = Depends(get_db)):
    """
    Manually publish a ready-for-sale build to eBay immediately, bypassing
    the deferred-listing scheduler. Requires eBay to be connected (Settings
    > Seller Policies > Connect eBay) — returns published: false with a
    clear reason otherwise, rather than silently doing nothing.
    """
    from app.workers.recreate_cycle import publish_flip_now

    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    if flip.stage != FlipStage.ready_for_sale:
        raise HTTPException(409, f"Flip must be in ready_for_sale stage to publish (currently {flip.stage.value}).")
    if flip.listed_at is not None:
        raise HTTPException(409, "Flip is already listed on eBay.")

    ok = await publish_flip_now(flip, db)
    await db.flush()

    if not ok:
        return {
            "published": False,
            "reason": "No eBay seller account connected — go to Settings > Seller Policies > Connect eBay first.",
        }
    return {"published": True, "ebay_listing_url": flip.ebay_listing_url}


@router.get("/{flip_id}/pricing-suggestions")
async def pricing_suggestions_endpoint(flip_id: int, db: AsyncSession = Depends(get_db)):
    """Rows 35/40: shipping-inclusive price + Promoted Listings ad-rate suggestion."""
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    listing = await db.get(Listing, flip.listing_id)

    base_price = flip.listing_price or flip.current_estimated_resale or flip.total_cost
    shipping = pricing_engine.shipping_inclusive_price(base_price, has_gpu=bool(listing.gpu) if listing else False)
    ad_rate = pricing_engine.suggest_promoted_ad_rate(
        estimated_profit=flip.current_estimated_profit or 0.0,
        total_cost=flip.total_cost,
    )
    return {"shipping": shipping, "promoted_listings": ad_rate}


@router.get("/{flip_id}/watcher-offer-plan")
async def watcher_offer_plan_endpoint(flip_id: int, db: AsyncSession = Depends(get_db)):
    """Row 45: whether a watcher offer is due right now, and what it should be."""
    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(404, "Flip not found")
    listing_price = flip.listing_price or flip.current_estimated_resale or flip.total_cost
    plan = offer_engine.evaluate_send_to_watchers(
        listing_price=listing_price,
        min_offer_price=flip.min_offer_price,
        listed_at=flip.listed_at,
        last_watcher_offer_sent_at=flip.last_watcher_offer_sent_at,
    )
    return {
        "should_send": plan.should_send,
        "discount_pct": plan.discount_pct,
        "offer_price": plan.offer_price,
        "reason": plan.reason,
    }


async def _recalculate_costs(flip: Flip, db: AsyncSession):
    listing = await db.get(Listing, flip.listing_id)
    upgrade_cost = 0.0
    for part_id in flip.selected_upgrade_ids.values():
        part = await db.get(Part, int(part_id))
        if part and part.price_used:
            upgrade_cost += part.price_used
    flip.upgrade_cost = upgrade_cost
    flip.total_cost = (listing.price if listing else flip.base_cost) + upgrade_cost
    if listing and listing.estimated_resale:
        fees = listing.estimated_resale * flip.platform_fee_pct
        flip.current_estimated_profit = listing.estimated_resale - flip.total_cost - fees


async def _derive_case_theme(flip: Flip, db: AsyncSession) -> str | None:
    """
    Resolve case theme from selected upgrades, if a case part is selected.
    Supports both keyed JSON (e.g. {"case": 123}) and arbitrary value maps.
    """
    selected = dict(flip.selected_upgrade_ids or {})
    if not selected:
        return None

    candidate_ids: list[int] = []
    if "case" in selected:
        try:
            candidate_ids.append(int(selected["case"]))
        except Exception as exc:
            log.warning("flips.case_id.invalid", value=selected.get("case"), error=str(exc))
    for _, v in selected.items():
        try:
            iv = int(v)
            if iv not in candidate_ids:
                candidate_ids.append(iv)
        except Exception:
            continue

    for part_id in candidate_ids:
        part = await db.get(Part, part_id)
        if not part:
            continue
        if str(part.category.value) == "case":
            return (part.theme or part.name or "").strip() or None
    return None
