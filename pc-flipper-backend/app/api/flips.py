from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.flip import Flip, FlipStage
from app.models.listing import Listing, ListingStatus, Classification
from app.models.part import Part
from app.models.flip_intelligence import FlipIntelligence
from app.schemas.flip import FlipOut, FlipCreate, FlipUpdate
from app.services.selling_toolkit import generate_titles, generate_description
from app.services import ai_service
from app.services.alerts import emit_alert
from app.config import get_settings
import structlog

settings = get_settings()
router = APIRouter(prefix="/flips", tags=["flips"])
log = structlog.get_logger(__name__)


@router.get("/", response_model=list[FlipOut])
@router.get("", response_model=list[FlipOut], include_in_schema=False)
async def get_flips(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Flip).order_by(Flip.created_at.desc()))
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
    await db.refresh(flip)
    return flip


@router.get("/{flip_id}", response_model=FlipOut)
async def get_flip(flip_id: int, db: AsyncSession = Depends(get_db)):
    flip = await db.get(Flip, flip_id)
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

    await db.flush()
    await db.refresh(flip)

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
    return flip


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
    cpu_tier = _extract_cpu_tier(listing.cpu if listing else None)

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


def _extract_cpu_tier(cpu: str | None) -> str | None:
    if not cpu:
        return None
    cpu_lower = cpu.lower()
    if "xeon" in cpu_lower:
        return "Xeon"
    if "i9" in cpu_lower:
        return "i9"
    if "i7" in cpu_lower:
        return "i7"
    if "i5" in cpu_lower:
        return "i5"
    if "i3" in cpu_lower:
        return "i3"
    if "ryzen 9" in cpu_lower:
        return "Ryzen 9"
    if "ryzen 7" in cpu_lower:
        return "Ryzen 7"
    if "ryzen 5" in cpu_lower:
        return "Ryzen 5"
    if "ryzen 3" in cpu_lower:
        return "Ryzen 3"
    return cpu.split()[0] if cpu else None


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
