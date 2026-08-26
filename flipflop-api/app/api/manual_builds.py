import json
import asyncio
import re
import uuid
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, Query
from jose import jwt
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import AsyncSessionLocal, get_db
from app.models.manual_build import ManualBuild
from app.models.gem_radar_intelligence import ComponentRatingEvent, PreferredComponent
from app.models.build import Build, BuildType, BuildStatus
from app.models.product import Product, ProductType, ProductStatus
from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.models.price_alert import PriceAlert
from app.models.admin_user import AdminUser
from app.schemas.manual_build import (
    ManualBuildCreate, ManualBuildPatch, ManualBuildOut, ManualBuildSummary,
    EvaluationResult, EvaluationSuggestion, GenerateListingResult,
    PostToEbayRequest, PostToEbayResult, SetHeroPhotoRequest, RemovePhotoRequest,
    ListOnStorefrontRequest, ListOnStorefrontResult, ReorderPhotosRequest,
    UpdateAspectsRequest, UpdateEbayListingConfigRequest, FulfillmentPolicyOut,
    CourierQuoteOut, InsuranceQuoteOut, SyncEbayOrderResult, BuyerAddressOut, BookShipmentRequest,
    BookShipmentResult, UpdateEvidenceDataRequest,
)
from app.services import ai_service
from app.services.ebay_listing_poster import post_flip_to_ebay, prepare_ebay_listing_description
from app.services.ebay_specifics_generator import (
    generate_item_specifics,
    repair_legacy_aspect_cardinality,
    validate_aspects_for_ebay,
)
from app.services.ebay_fulfillment_policies import (
    list_fulfillment_policies,
    EbayFulfillmentPoliciesError,
)
from app.services.parcel2go_courier import get_tracked_quotes, Parcel2GoError
from app.services.figural_insurance import get_insurance_quote, FiguralError
from app.services.ebay_order_sync import find_order_for_listing, EbayOrderSyncError, BuyerAddress
from app.services.parcel2go_booking import (
    create_order as create_parcel2go_order,
    pay_order_with_prepay,
    Parcel2GoBookingError,
)
from app.services.ebay_shipping_fulfillment import mark_order_shipped, EbayShippingFulfillmentError
from app.services.ebay_listing_withdraw import withdraw_listing_by_sku, EbayListingWithdrawError
from app.services.cross_channel_guard import withdraw_storefront_for_sold_build
from app.services.media_sync import sync_to_public_media
from app.services.meshy_generation import generate_multi_image_asset
from app.services.product_faqs import FAQ_BANK, FAQ_BY_ID, selected_faqs, render_ebay_faq_html
from app.services import pricing_engine
import structlog

log = structlog.get_logger(__name__)
from app.config import get_settings
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/manual-builds", tags=["manual-builds"], dependencies=[Depends(get_current_admin)])


class ComponentRatingInput(BaseModel):
    component_slot: str
    component_key: str
    overall_rating: int = Field(ge=1, le=5)
    reliability_rating: int | None = Field(default=None, ge=1, le=5)
    installation_rating: int | None = Field(default=None, ge=1, le=5)
    aesthetics_rating: int | None = Field(default=None, ge=1, le=5)
    value_rating: int | None = Field(default=None, ge=1, le=5)
    customer_appeal_rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class ComponentRatingsInput(BaseModel):
    ratings: list[ComponentRatingInput]


class ComponentPurchaseInput(BaseModel):
    price_paid: float | None = Field(default=None, ge=0)
    source: str | None = None


class FaqSelectionInput(BaseModel):
    selected_ids: list[str] = Field(max_length=10)
    answer_overrides: dict[str, str] = Field(default_factory=dict)


class QueueBuild3DAssetsInput(BaseModel):
    assets: dict[str, list[str]]


@router.post("/{build_id}/portal-preview")
async def create_build_portal_preview(
    build_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Create a read-only owner-portal preview for a completed physical build."""
    build = (await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id)
    )).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status not in {"built", "listed", "sold"}:
        raise HTTPException(status_code=409, detail="The customer portal is created when the build reaches Built")
    if not build.model_3d_url:
        raise HTTPException(status_code=409, detail="Complete the build's 3D model to create its customer portal")

    product = None
    if build.storefront_product_id:
        product = (await db.execute(
            select(Product).where(Product.id == build.storefront_product_id)
        )).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    settings = get_settings()
    token = jwt.encode(
        {
            "typ": "portal_preview",
            "build_id": build.id,
            "order_id": product.sold_order_id if product else None,
            "scope": "read",
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {
        # The storefront route historically calls this value order_id. Before
        # sale, the build id provides a stable route segment; the signed token
        # remains the authority for selecting portal data.
        "order_id": product.sold_order_id if product and product.sold_order_id else build.id,
        "build_id": build.id,
        "token": token,
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
    }


async def _run_build_3d_generation(build_id: int, requested: dict[str, list[str]]) -> None:
    """Run Meshy jobs off-request, mirror expiring results, then persist once."""
    results = await asyncio.gather(
        *(generate_multi_image_asset(urls) for urls in requested.values()),
        return_exceptions=True,
    )
    completed: dict[str, dict] = {}
    for (asset_type, source_urls), result in zip(requested.items(), results):
        entry = {"provider": "meshy", "source_image_urls": source_urls}
        if isinstance(result, Exception) or result is None:
            entry.update(status="failed", error=str(result) if result else "Meshy did not accept the task")
        elif result.status != "SUCCEEDED" or not result.glb_url:
            entry.update(status="failed", task_id=result.task_id, error=f"Meshy task ended as {result.status}")
        else:
            try:
                filename = f"build_{build_id}_{asset_type}_{uuid.uuid4().hex}.glb"
                local_path = _PUBLIC_MEDIA_ROOT / filename
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    response = await client.get(result.glb_url)
                    response.raise_for_status()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(response.content)
                await sync_to_public_media(local_path)
                entry.update(
                    status="succeeded",
                    task_id=result.task_id,
                    glb_url=f"https://theflipflop.shop/media/{filename}",
                    preview_url=result.thumbnail_url,
                    completed_at=datetime.utcnow().isoformat(),
                )
            except Exception as exc:
                entry.update(status="failed", task_id=result.task_id, error=f"Could not store GLB: {exc}")
        completed[asset_type] = entry

    async with AsyncSessionLocal() as session:
        build = (await session.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
        if not build:
            return
        assets = dict(build.model_3d_assets or {})
        assets.update(completed)
        build.model_3d_assets = assets
        if completed.get("complete_build", {}).get("status") == "succeeded":
            build.model_3d_url = completed["complete_build"]["glb_url"]
        await session.commit()


@router.post("/{build_id}/model-3d/generate", status_code=202)
async def queue_build_3d_generation(
    build_id: int,
    body: QueueBuild3DAssetsInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    unknown = set(body.assets) - {"complete_build"}
    if unknown:
        raise HTTPException(status_code=422, detail="Only complete-build photos can be selected manually")
    complete_build_urls = body.assets.get("complete_build", [])
    if not complete_build_urls:
        raise HTTPException(status_code=422, detail="Select photos of the real completed PC")
    valid_urls = {p.get("url") for p in (build.photos or []) if p.get("kind") == "photo"}
    if not 1 <= len(complete_build_urls) <= 4:
        raise HTTPException(status_code=422, detail="The complete build needs 1 to 4 photos")
    if len(set(complete_build_urls)) != len(complete_build_urls) or any(url not in valid_urls for url in complete_build_urls):
        raise HTTPException(status_code=422, detail="The complete build contains an invalid or duplicate photo")

    requested = {"complete_build": complete_build_urls}

    assets = dict(build.model_3d_assets or {})
    queued_at = datetime.utcnow().isoformat()
    for asset_type, urls in requested.items():
        assets[asset_type] = {
            "provider": "meshy",
            "status": "queued",
            "source_image_urls": urls,
            "queued_at": queued_at,
        }
    build.model_3d_assets = assets
    await db.commit()
    background_tasks.add_task(_run_build_3d_generation, build_id, requested)
    return {"queued": list(requested), "assets": assets}


def _description_with_selected_faqs(description: str, build: ManualBuild) -> str:
    """Replace any previously-rendered FAQ block with the current selection."""
    without_old = re.sub(
        r'<section data-flipflop-faq="true".*?</section>',
        "",
        description,
        flags=re.DOTALL,
    )
    items = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
    return without_old + (render_ebay_faq_html(items) if items else "")

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB
_UPLOADS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "manual_builds"
_PUBLIC_MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "FlipFlop.shop" / "public" / "media"
_SELLING_PRINCIPLES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "selling_principles.md"
_EBAY_LISTING_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ebay_listing_system_prompt.md"

# HERO_IMAGE_URL is the one listing-template placeholder the LLM is
# instructed NOT to fill in itself (see ebay_listing_system_prompt.md) — it
# varies per build, so only this backend can know the right value. Filled in
# deterministically below from build.hero_photo_url, which is set the moment
# a build's first photo is uploaded (see the photo-upload endpoint below).
# The flipflop logo URL used to be a similarly LLM-filled placeholder too,
# but that one never varies between builds, so it's now hardcoded straight
# into the template itself — nothing left to substitute for it here.

# eBay Item Specifics for category 179 (PC Desktops & All-in-Ones), fetched
# from the Taxonomy API's get_item_aspects_for_category. "Brand" and "Type"
# are eBay-required; the rest are recommended and materially improve
# listing visibility/trust when filled in.
_EBAY_CATEGORY_179_ASPECTS = [
    "Brand", "Type", "Model", "Most Suitable For", "MPN", "Form Factor",
    "Storage Type", "Hard Drive Capacity", "Processor", "Processor Speed",
    "RAM Size", "Operating System", "Connectivity", "Features", "GPU",
    "Series", "Graphics Processing Type", "Manufacturer Warranty",
    "Country of Origin", "Colour", "Maximum RAM Capacity",
    "Motherboard Model", "Release Year", "SSD Capacity",
]


def _load_selling_principles() -> str:
    """Read fresh on every call so edits to the file take effect immediately."""
    try:
        return _SELLING_PRINCIPLES_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_ebay_listing_system_prompt() -> str:
    """Read fresh on every call so edits to the file take effect immediately."""
    return _EBAY_LISTING_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _load_build_performance_evidence(build_name: str) -> dict | None:
    """Load reviewed, build-specific evidence when it is not yet in the DB."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", build_name.lower()).strip("-")
    path = _EBAY_LISTING_SYSTEM_PROMPT_PATH.parent / "build_evidence" / f"{slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_section(text: str, start_marker: str, end_markers: list[str]) -> str:
    """Extract text between a section header and whichever of the given
    next-section headers appears first — tolerant of the model reformatting
    the exact separator characters around each header."""
    m = re.search(re.escape(start_marker), text, re.IGNORECASE)
    if not m:
        return ""
    start = m.end()
    end = len(text)
    for marker in end_markers:
        m2 = re.search(re.escape(marker), text[start:], re.IGNORECASE)
        if m2:
            end = min(end, start + m2.start())
    return text[start:end].strip()


def _extract_recommended_title(text: str) -> str | None:
    # Find section B
    b_idx = text.upper().find("B.")
    if b_idx < 0:
        return None
    # Find where section B ends (at C. or end of text)
    c_idx = text.upper().find("\nC.", b_idx)
    if c_idx < 0:
        c_idx = len(text)
    section = text[b_idx:c_idx]

    # Extract title-like lines (skip the header "B. Three eBay titles")
    for line in section.splitlines()[1:]:  # Skip first line (the header)
        stripped = line.strip()
        if stripped and len(stripped) < 85 and not stripped.startswith(("-", "*", "#")):
            return stripped
    return None


def _extract_html_section(text: str) -> str | None:
    # Find section D
    d_idx = text.upper().find("\nD.")
    if d_idx < 0:
        # Try without newline (if D. is at start)
        d_idx = text.upper().find("D.")
    if d_idx < 0:
        return None

    # Find where section D ends (at E. or end of text)
    e_idx = text.upper().find("\nE.", d_idx)
    if e_idx < 0:
        e_idx = len(text)
    section = text[d_idx:e_idx].strip()

    # Skip the header line "D. Complete branded HTML description"
    lines = section.splitlines()
    section = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # Look for the start of HTML
    html_match = re.search(r"<(div|html|!doctype)", section, re.IGNORECASE)
    if html_match:
        return section[html_match.start():].strip()

    return None


@router.post("/", response_model=ManualBuildOut, status_code=201)
async def create_build(body: ManualBuildCreate, db: AsyncSession = Depends(get_db)):
    build = ManualBuild(name=body.name, components=[], total_cost=None)
    db.add(build)
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/", response_model=list[ManualBuildSummary])
async def list_builds(include_archived: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(ManualBuild).order_by(ManualBuild.updated_at.desc())
    if not include_archived:
        query = query.where(ManualBuild.is_archived.is_(False))
    result = await db.execute(query)
    builds = result.scalars().all()
    return [
        ManualBuildSummary(
            id=b.id,
            name=b.name,
            total_cost=b.total_cost,
            component_count=len(b.components or []),
            status=b.status,
            updated_at=b.updated_at,
        )
        for b in builds
    ]


@router.get("/ebay-fulfillment-policies", response_model=list[FulfillmentPolicyOut])
async def get_ebay_fulfillment_policies():
    """Real shipping-destination options for the Shipping & Delivery section
    — fetched live from the seller's own eBay account, not a hardcoded list.
    Uses whichever environment (sandbox/production) is currently configured
    for listing, same as post_to_ebay. MUST stay registered before
    GET /{build_id} below — Starlette matches routes by position, and
    /{build_id} would otherwise swallow this path first and 422 on failing
    to parse "ebay-fulfillment-policies" as an int."""
    settings = get_settings()
    try:
        policies = await list_fulfillment_policies(settings.ebay_listing_environment)
    except EbayFulfillmentPoliciesError as e:
        raise HTTPException(
            e.status_code or 502,
            f"Couldn't fetch fulfillment policies from eBay: {e}. "
            "If this is a 403, the stored eBay OAuth token likely wasn't granted "
            "the sell.account scope — it needs to be re-authorized.",
        )
    return [
        FulfillmentPolicyOut(
            policy_id=p.policy_id,
            name=p.name,
            marketplace_id=p.marketplace_id,
            ship_to_regions=p.ship_to_regions,
            handling_time_days=p.handling_time_days,
        )
        for p in policies
    ]


@router.get("/{build_id}/faqs")
async def get_build_faqs(build_id: int, db: AsyncSession = Depends(get_db)):
    build = (
        await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    ).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    effective = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
    return {
        "bank": FAQ_BANK,
        "selected_ids": [item["id"] for item in effective],
        "uses_defaults": build.selected_faq_ids is None,
        "answer_overrides": build.selected_faq_answer_overrides or {},
        "maximum": 10,
    }


@router.put("/{build_id}/faqs")
async def update_build_faqs(
    build_id: int, body: FaqSelectionInput, db: AsyncSession = Depends(get_db)
):
    build = (
        await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    ).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if len(body.selected_ids) != len(set(body.selected_ids)):
        raise HTTPException(400, "FAQ selections must be unique")
    unknown = [item_id for item_id in body.selected_ids if item_id not in FAQ_BY_ID]
    if unknown:
        raise HTTPException(400, f"Unknown FAQ IDs: {', '.join(unknown)}")
    unknown_overrides = [item_id for item_id in body.answer_overrides if item_id not in FAQ_BY_ID]
    if unknown_overrides:
        raise HTTPException(400, f"Unknown FAQ override IDs: {', '.join(unknown_overrides)}")
    cleaned_overrides = {
        item_id: answer.strip()
        for item_id, answer in body.answer_overrides.items()
        if answer.strip() and answer.strip() != FAQ_BY_ID[item_id]["answer"]
    }
    build.selected_faq_ids = body.selected_ids
    build.selected_faq_answer_overrides = cleaned_overrides
    if build.generated_description:
        build.generated_description = prepare_ebay_listing_description(
            _description_with_selected_faqs(build.generated_description, build)
        )
    if build.storefront_product_id:
        product = (
            await db.execute(select(Product).where(Product.id == build.storefront_product_id))
        ).scalar_one_or_none()
        if product:
            product.selected_faqs = selected_faqs(build.id, body.selected_ids, cleaned_overrides)
    build.updated_at = datetime.utcnow()
    await db.flush()
    return {"selected_ids": body.selected_ids, "answer_overrides": cleaned_overrides, "selected_faqs": selected_faqs(build.id, body.selected_ids, cleaned_overrides)}


@router.get("/{build_id}", response_model=ManualBuildOut)
async def get_build(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    # eBay is authoritative. Poll at most once per minute while this detail
    # view is being opened/refreshed; a transient API failure remains unknown
    # and never grants permission to create a duplicate listing.
    if build.ebay_listing_id:
        try:
            from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
            await reconcile_manual_build_listing(build, db)
        except Exception as exc:
            log.warning("manual_build.ebay_reconcile_on_read_failed", build_id=build.id, error=str(exc))
            build.ebay_listing_status = "unknown"
    else:
        build.ebay_listing_status = "never_listed"
    build.ebay_live = build.ebay_listing_status == "active"
    build.storefront_live = False
    if build.storefront_product_id:
        from app.models.product import Product, ProductStatus
        product_result = await db.execute(
            select(Product).where(Product.id == build.storefront_product_id)
        )
        product = product_result.scalar_one_or_none()
        build.storefront_live = bool(product and product.status == ProductStatus.LISTED)

    return build


@router.patch("/{build_id}", response_model=ManualBuildOut)
async def patch_build(build_id: int, body: ManualBuildPatch, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if body.name is not None:
        build.name = body.name
    if body.components is not None:
        build.components = [c.model_dump() for c in body.components]
        build.total_cost = sum(c.price_paid for c in body.components)
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/components/{slot}/purchase", response_model=ManualBuildOut)
async def purchase_build_component(
    build_id: int,
    slot: str,
    body: ComponentPurchaseInput,
    db: AsyncSession = Depends(get_db),
):
    """Record an external component purchase and reserve it to this draft."""
    from app.services.inventory_lifecycle import add_event, orchestration_build_for

    build = await db.get(ManualBuild, build_id)
    if not build or build.is_archived:
        raise HTTPException(404, "Build not found")
    if build.status != "in_progress":
        raise HTTPException(400, "Only draft builds can record component purchases")
    components = list(build.components or [])
    index = next((i for i, component in enumerate(components) if component.get("slot") == slot), None)
    if index is None:
        raise HTTPException(404, f"Component slot {slot} not found")
    component = dict(components[index])
    if component.get("inventory_item_id"):
        component["purchased"] = True
        components[index] = component
        build.components = components
        await db.flush()
        await db.refresh(build)
        return build

    component_type_by_slot = {
        "cpu": "cpu", "gpu": "gpu", "ram": "ram", "motherboard": "motherboard",
        "storage": "ssd", "ssd": "ssd", "psu": "psu", "pc case": "case",
        "case": "case", "cpu cooler": "cooler", "cooler": "cooler",
    }
    item = InventoryItem(
        component_name=component.get("name") or slot,
        component_type=component_type_by_slot.get(slot.lower(), slot.lower().replace(" ", "_")),
        quantity=1,
        base_price=body.price_paid if body.price_paid is not None else float(component.get("price_paid") or 0),
        shipping_cost=0,
        discount_amount=0,
        purchase_date=datetime.utcnow(),
        source=body.source or "Build purchase",
        notes=f"Purchased for draft build: {build.name}",
        listing_url=component.get("listing_url"),
        purchase_status="PURCHASED",
        reconciliation_status="PENDING" if component.get("listing_url") else "NOT_APPLICABLE",
    )
    db.add(item)
    await db.flush()
    orchestration = await orchestration_build_for(db, build)
    allocation = InventoryAllocation(
        inventory_item_id=item.id,
        build_id=orchestration.id,
        flip_id=None,
        quantity_allocated=1,
        cost_per_unit_at_allocation=item.actual_cost,
        notes=f"Reserved for draft build: {build.name}",
    )
    db.add(allocation)
    component["price_paid"] = item.actual_cost
    component["purchased"] = True
    component["inventory_item_id"] = item.id
    components[index] = component
    build.components = components
    build.total_cost = sum(float(existing.get("price_paid") or 0) for existing in components)
    add_event(db, inventory_item_id=item.id, manual_build_id=build.id, event_type="purchased", quantity=1,
              detail={"source": item.source, "listing_url": item.listing_url})
    add_event(db, inventory_item_id=item.id, manual_build_id=build.id, event_type="reserved", quantity=1,
              detail={"build_name": build.name})
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}", status_code=204)
async def delete_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """Archives the build rather than deleting it.

    A hard delete here previously left any live eBay listing (ebay_listing_id/
    ebay_sku) with no local record at all — orphaned from every reprice, Best
    Offer, and relist automation, and untraceable since the delete wasn't
    logged. Archiving keeps the row (and those eBay identifiers) intact so
    it can still be found and reconciled later.
    """
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    from app.services.inventory_lifecycle import release_manual_build_inventory
    await release_manual_build_inventory(db, build, reason="draft archived")
    build.is_archived = True
    build.updated_at = datetime.utcnow()
    await db.flush()


@router.post("/{build_id}/evaluate", response_model=EvaluationResult)
async def evaluate_build(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.components:
        raise HTTPException(400, "Build has no components to evaluate")

    # Format component list for the prompt
    lines = []
    for c in build.components:
        name = c["name"] if isinstance(c, dict) else c.name
        slot = c["slot"] if isinstance(c, dict) else c.slot
        price = c["price_paid"] if isinstance(c, dict) else c.price_paid
        lines.append(f"  - {slot}: {name} (paid £{price:.0f})")
    component_text = "\n".join(lines)
    total = build.total_cost or sum(
        (c["price_paid"] if isinstance(c, dict) else c.price_paid)
        for c in build.components
    )

    prompt = f"""I have assembled a PC build for resale in the UK secondhand market. Here are the components and what I paid:

{component_text}

Total cost: £{total:.0f}

Please assess this build and respond with ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "low": <number>,
  "mid": <number>,
  "high": <number>,
  "narrative": "<2-3 sentence assessment>",
  "suggestions": [
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}}
  ]
}}

low/mid/high = estimated resale prices in GBP. uplift = estimated price increase in GBP from that suggestion. Max 3 suggestions. Be realistic about UK eBay/Gumtree prices."""

    response_text, _model = await ai_service.chat(prompt, history=[])
    if _model == "none":
        raise HTTPException(503, response_text)

    # Parse JSON from response — strip any accidental markdown fences
    raw = response_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise HTTPException(502, f"LLM returned unparseable response: {raw[:200]}")
        data = json.loads(match.group())

    result = EvaluationResult(
        low=float(data.get("low", 0)),
        mid=float(data.get("mid", 0)),
        high=float(data.get("high", 0)),
        narrative=data.get("narrative", ""),
        suggestions=[
            EvaluationSuggestion(text=s["text"], uplift=float(s.get("uplift", 0)))
            for s in data.get("suggestions", [])[:3]
        ],
    )

    # Persist evaluation result back to the build
    build.last_evaluation = result.model_dump()
    build.updated_at = datetime.utcnow()
    await db.flush()

    return result


@router.post("/{build_id}/mark-built", response_model=ManualBuildOut)
async def mark_built(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.components:
        raise HTTPException(400, "Build has no components")

    unpurchased = [
        (c["slot"] if isinstance(c, dict) else c.slot)
        for c in build.components
        if not (c.get("purchased") if isinstance(c, dict) else c.purchased)
    ]
    if unpurchased:
        raise HTTPException(
            400,
            f"Every component must be marked purchased first — still waiting on: {', '.join(unpurchased)}",
        )

    build.status = "built"
    build.updated_at = datetime.utcnow()
    from app.services.inventory_lifecycle import record_consumption
    await record_consumption(db, build)

    # Rows 10/33/19/20: demand check + initial pricing anchor/floor fire
    # automatically once cost is finalized (all components purchased), no
    # click needed — mirrors the retired Flip system's create_flip hook.
    try:
        from app.services import demand_check as demand_check_service
        from app.services.pricing_engine import _component_spec

        signal = await demand_check_service.check_demand(
            _component_spec(build, "CPU"), _component_spec(build, "GPU")
        )
        build.demand_sold_count_90d = signal.sold_count_90d
        build.demand_active_count = signal.active_count
        build.demand_checked_at = signal.checked_at
    except Exception as exc:
        log.warning("manual_builds.demand_check.failed", build_id=build.id, error=str(exc))

    try:
        await pricing_engine.recalculate_manual_build_pricing(build, db)
    except Exception as exc:
        log.warning("manual_builds.pricing_recalc.failed", build_id=build.id, error=str(exc))

    await db.flush()
    await db.refresh(build)
    return build


@router.get("/{build_id}/component-ratings")
async def get_component_ratings(build_id: int, db: AsyncSession = Depends(get_db)):
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    ratings = (await db.execute(
        select(ComponentRatingEvent).where(ComponentRatingEvent.build_id == build_id)
    )).scalars().all()
    return [{
        "component_slot": rating.component_slot, "component_key": rating.component_key,
        "overall_rating": rating.overall_rating, "reliability_rating": rating.reliability_rating,
        "installation_rating": rating.installation_rating, "aesthetics_rating": rating.aesthetics_rating,
        "value_rating": rating.value_rating, "customer_appeal_rating": rating.customer_appeal_rating,
        "notes": rating.notes,
    } for rating in ratings]


@router.put("/{build_id}/component-ratings")
async def save_component_ratings(
    build_id: int,
    body: ComponentRatingsInput,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status not in ("built", "listed", "sold"):
        raise HTTPException(400, "Component ratings become available after the build is marked built")
    valid_components = {
        (str(component.get("slot", "")).lower(), str(component.get("name", "")).strip().lower())
        for component in build.components if isinstance(component, dict)
    }
    alerts_created = 0
    alerts_updated = 0
    for incoming in body.ratings:
        identity = (incoming.component_slot.lower(), incoming.component_key.strip().lower())
        if identity not in valid_components:
            raise HTTPException(400, f"{incoming.component_slot}: component does not match this build")
        rating = (await db.execute(select(ComponentRatingEvent).where(
            ComponentRatingEvent.build_id == build_id,
            ComponentRatingEvent.component_slot == incoming.component_slot,
            ComponentRatingEvent.component_key == incoming.component_key,
        ))).scalar_one_or_none()
        values = incoming.model_dump()
        was_five_star = rating is not None and rating.overall_rating == 5
        if rating is None:
            rating = ComponentRatingEvent(build_id=build_id, **values)
            db.add(rating)
        else:
            for key, value in values.items():
                setattr(rating, key, value)
            rating.updated_at = datetime.utcnow()

        preferred = (await db.execute(select(PreferredComponent).where(
            PreferredComponent.component_key == incoming.component_key
        ))).scalar_one_or_none()
        if incoming.overall_rating == 5 and not was_five_star:
            if preferred is None:
                db.add(PreferredComponent(
                    component_key=incoming.component_key, component_slot=incoming.component_slot,
                    sample_count=1, average_rating=5.0, status="preferred",
                    last_build_id=build_id, last_used_at=datetime.utcnow(),
                ))
            else:
                preferred.average_rating = (
                    preferred.average_rating * preferred.sample_count + incoming.overall_rating
                ) / (preferred.sample_count + 1)
                preferred.sample_count += 1
                preferred.status = "preferred"
                preferred.last_build_id = build_id
                preferred.last_used_at = datetime.utcnow()
        if incoming.overall_rating == 5:
            component = next(
                item for item in build.components
                if str(item.get("slot", "")).lower() == incoming.component_slot.lower()
                and str(item.get("name", "")).strip().lower() == incoming.component_key.strip().lower()
            )
            # Use the same source-backed component valuation shown in Pricing.
            # If market evidence is sparse, estimated_resale already falls back
            # transparently to recorded market/paid value.
            from app.api.builds_pricing import _component_valuations
            valuation = (await _component_valuations([component]))[0]
            market_reference = max(0.01, valuation.estimated_resale)
            target_pennies = round(market_reference * 0.85 * 100)
            reference_pennies = round(market_reference * 100)
            alert = (await db.execute(select(PriceAlert).where(
                PriceAlert.alert_type == "component",
                PriceAlert.component_key == incoming.component_key,
            ))).scalar_one_or_none()
            if alert is None:
                db.add(PriceAlert(
                    manual_build_id=None,
                    alert_type="component",
                    component_key=incoming.component_key,
                    component_slot=incoming.component_slot,
                    market_reference_price_gbp=reference_pennies,
                    discount_threshold_pct=15.0,
                    target_price_gbp=target_pennies,
                    user_email=admin.email,
                    is_active=True,
                ))
                alerts_created += 1
            else:
                alert.component_slot = incoming.component_slot
                alert.market_reference_price_gbp = reference_pennies
                alert.discount_threshold_pct = 15.0
                alert.target_price_gbp = target_pennies
                alert.user_email = admin.email
                alert.is_active = True
                alert.triggered_at = None
                alert.triggered_price_gbp = None
                alerts_updated += 1
    await db.flush()
    return {
        "saved": len(body.ratings),
        "preferred_added": sum(r.overall_rating == 5 for r in body.ratings),
        "alerts_created": alerts_created,
        "alerts_updated": alerts_updated,
    }


@router.post("/{build_id}/generate-listing", response_model=GenerateListingResult)
async def generate_listing(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status not in ("built", "listed", "sold"):
        raise HTTPException(400, "Build must be marked built before generating a listing")

    lines = []
    for c in build.components:
        name = c["name"] if isinstance(c, dict) else c.name
        slot = c["slot"] if isinstance(c, dict) else c.slot
        lines.append(f"  - {slot}: {name}")
    component_text = "\n".join(lines)

    system_prompt = _load_ebay_listing_system_prompt()
    selling_principles = _load_selling_principles()

    # This build's own evidence — spec card and registration plate data are
    # entirely derivable from fields already on the build (components,
    # name), so they're auto-populated unless the seller has uploaded more
    # specific JSON via PUT /{build_id}/evidence-data. Performance data has
    # no such fallback — it only exists if uploaded for this exact build.
    # All of it goes to the LLM as plain JSON text, never as an image —
    # no vision model involved.
    evidence = build.evidence_data or {}
    spec_card_data = evidence.get("spec_card") or {
        "pc_name": build.name,
        "components": [
            {"slot": (c["slot"] if isinstance(c, dict) else c.slot), "name": (c["name"] if isinstance(c, dict) else c.name)}
            for c in build.components
        ],
    }
    registration_plate_data = evidence.get("registration_plate") or {"pc_name": build.name}
    performance_card_data = evidence.get("performance_card") or _load_build_performance_evidence(build.name)

    shipping_labels = {
        "tracked": "Tracked courier delivery",
        "untracked": "Untracked delivery",
        "local_pickup": "Local pickup",
    }
    delivery_method = shipping_labels.get(build.shipping_method, build.shipping_method or "Not set")

    materials = f"""ITEM TYPE: Desktop PC
BRAND: flipflop
PRODUCT NAME: {build.name}
EBAY CATEGORY: PC Desktops & All-in-Ones
CONDITION SELECTION: {build.ebay_condition or "Not set"}

FULL SPECIFICATIONS:
{component_text}

SPECIFICATION CARD DATA (JSON):
{json.dumps(spec_card_data, indent=2)}

REGISTRATION PLATE DATA (JSON):
{json.dumps(registration_plate_data, indent=2)}

MEASURED BENCHMARKS / TEMPERATURES / STABILITY RESULTS (JSON):
{json.dumps(performance_card_data, indent=2) if performance_card_data else "None supplied — omit the PERFORMANCE YOU CAN COUNT ON section or place it under INFORMATION REQUIRED"}

RETURNS POLICY: {f"{build.return_days} day returns" if build.return_days else "No voluntary returns period set"}
CHANGE-OF-MIND RETURN POSTAGE: Customer pays the return postage. The PC must be returned securely packed and in the condition received.
FAULTY / DAMAGED / MISDESCRIBED RETURN POSTAGE: flipflop pays the reasonable return postage.
CONSUMER RIGHTS: The buyer's UK statutory rights are not affected. A faulty or misdescribed item remains covered by those rights regardless of the voluntary returns period.
SUPPORT: Direct setup and after-sales support is available from flipflop. Manufacturer warranties are passed on where transferable.

DELIVERY METHOD: {delivery_method}
DISPATCH TIME: {build.handling_time_days} business day(s)
COLLECTION AVAILABLE: No — delivery only, collection is never offered on any listing
COLLECTION TESTING AVAILABLE: Not applicable — no collection offered

PRICE: {f"£{build.ebay_price}" if build.ebay_price else "Not yet set"}
BEST OFFER ENABLED: {"Yes" if build.allow_offers else "No"}
"""

    if selling_principles:
        materials += f"\n\nADDITIONAL SELLER GUIDANCE (house style — follow alongside the system instructions above):\n{selling_principles}\n"

    try:
        raw_response, _model = await ai_service.generate_ebay_listing(system_prompt, materials)
    except ValueError as e:
        raise HTTPException(503, f"OpenRouter API not configured: {str(e)}")
    except Exception as e:
        raise HTTPException(502, f"Listing generation failed: {str(e)}")

    title = _extract_recommended_title(raw_response)
    description_html = _extract_html_section(raw_response)

    if not title or not description_html:
        raise HTTPException(
            502,
            "The AI response didn't include a parseable title or HTML section — "
            f"raw response (first 800 chars): {raw_response[:800]}",
        )

    if build.hero_photo_url:
        description_html = description_html.replace("{{HERO_IMAGE_URL}}", build.hero_photo_url)
    elif "{{HERO_IMAGE_URL}}" in description_html:
        import structlog

        structlog.get_logger(__name__).warning(
            "generate_listing.hero_image_placeholder_unfilled",
            build_id=build_id,
            reason="build has no hero_photo_url set — upload a photo first",
        )

    prepared_description = prepare_ebay_listing_description(
        _description_with_selected_faqs(description_html, build)
    )
    build.generated_title = title[:80]
    build.generated_description = prepared_description
    build.updated_at = datetime.utcnow()
    await db.flush()

    return GenerateListingResult(
        titles=[title],
        description=prepared_description,
        aspects=build.generated_aspects or {},
    )


@router.post("/{build_id}/generate-specifics", response_model=GenerateListingResult)
async def generate_specifics(build_id: int, db: AsyncSession = Depends(get_db)):
    """Generate eBay Item Specifics using LLM with validated eBay values only."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.components:
        raise HTTPException(400, "Build must have components to generate specifics")

    selling_principles = _load_selling_principles()
    aspects = await generate_item_specifics(build, selling_principles)

    build.generated_aspects = aspects
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)

    return GenerateListingResult(
        titles=build.generated_title.split(",") if build.generated_title else [],
        description=build.generated_description or "",
        aspects=aspects
    )


@router.post("/{build_id}/courier-quote", response_model=list[CourierQuoteOut])
async def get_courier_quote(
    build_id: int, delivery_country: str | None = None, db: AsyncSession = Depends(get_db)
):
    """Cheapest real tracked-delivery quote for this build's saved package
    dimensions, via Parcel2Go — see app/services/parcel2go_courier.py.
    Requires package_weight_kg/length_cm/width_cm/height_cm to already be
    set on the build (via PATCH .../ebay-config) — deliberately doesn't
    guess them from components."""
    import structlog
    log = structlog.get_logger(__name__)

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    log.info("courier_quote.request", build_id=build_id,
             weight=build.package_weight_kg, length=build.package_length_cm,
             width=build.package_width_cm, height=build.package_height_cm,
             ebay_price=build.ebay_price, total_cost=build.total_cost)

    missing = [
        field
        for field in ("package_weight_kg", "package_length_cm", "package_width_cm", "package_height_cm")
        if getattr(build, field) is None
    ]
    if missing:
        log.warning("courier_quote.missing_dimensions", build_id=build_id, missing=missing)
        raise HTTPException(
            400,
            f"Set the build's package dimensions first (missing: {', '.join(missing)}) "
            "before requesting a courier quote.",
        )

    # Prefer the real sale price once the build has actually sold and synced
    # (see sync_ebay_order below) — ebay_price/total_cost are pre-sale
    # estimates. Parcel2Go requires a non-zero insurance value either way.
    value_gbp = build.sale_price_actual or build.ebay_price or build.total_cost
    if not value_gbp or value_gbp <= 0:
        log.warning("courier_quote.zero_value", build_id=build_id, ebay_price=build.ebay_price, total_cost=build.total_cost)
        raise HTTPException(
            400,
            "Set either ebay_price or total_cost (must be > £0) before requesting a courier quote."
        )

    # If the real buyer address has been synced, default to their actual
    # country rather than assuming domestic GBR.
    resolved_country = delivery_country
    if resolved_country is None:
        resolved_country = (build.buyer_address_json or {}).get("country_code")
        if resolved_country == "GB":
            resolved_country = "GBR"
    resolved_country = resolved_country or "GBR"

    try:
        quotes = await get_tracked_quotes(
            weight_kg=build.package_weight_kg,
            length_cm=build.package_length_cm,
            width_cm=build.package_width_cm,
            height_cm=build.package_height_cm,
            value_gbp=value_gbp,
            delivery_country=resolved_country,
        )
    except Parcel2GoError as e:
        raise HTTPException(e.status_code or 502, str(e))

    if not quotes:
        raise HTTPException(404, "No tracked courier service found for this destination/parcel size")

    return [CourierQuoteOut(
        courier_name=quote.courier_name, service_name=quote.service_name,
        price_gbp=quote.price_gbp, tracked=quote.tracked,
        estimated_days=quote.estimated_days, service_slug=quote.service_slug,
        protection_scope=quote.protection_scope,
        full_value_damage_cover=quote.full_value_damage_cover,
        protection_warning=quote.protection_warning,
    ) for quote in quotes]


@router.post("/{build_id}/insurance-quote", response_model=InsuranceQuoteOut)
async def get_build_insurance_quote(
    build_id: int,
    listing_value_gbp: float = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Get a live Figural premium for the full current listing value.

    Price lookup only: this endpoint cannot create, reserve, or charge for an
    insurance policy. Cover is purchased later, after the item sells.
    """
    result = await db.execute(select(ManualBuild.id).where(ManualBuild.id == build_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, "Build not found")
    try:
        quote = await get_insurance_quote(listing_value_gbp)
    except FiguralError as error:
        raise HTTPException(error.status_code or 502, str(error))
    return InsuranceQuoteOut(
        provider="Figural",
        insured_value_gbp=quote.insured_value_gbp,
        price_gbp=quote.price_gbp,
        currency=quote.currency,
    )


@router.post("/{build_id}/sync-ebay-order", response_model=SyncEbayOrderResult)
async def sync_ebay_order(build_id: int, db: AsyncSession = Depends(get_db)):
    """Fetches this build's real eBay order — buyer name, actual delivery
    address, actual sale price — once it's sold. This data only exists
    after a real buyer has paid; it's never available at listing time.
    Requires ebay_listing_id to already be set (i.e. the build was actually
    posted to eBay). Safe to call again later — it just re-fetches and
    overwrites with the current order state."""
    # Unlocked existence/precondition check first — fast-fail path, no lock
    # held across the eBay API call below.
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.ebay_listing_id:
        raise HTTPException(400, "This build has no eBay listing ID — it hasn't been posted to eBay yet.")

    settings = get_settings()
    try:
        order = await find_order_for_listing(
            build.ebay_listing_id, environment=settings.ebay_listing_environment
        )
    except EbayOrderSyncError as e:
        raise HTTPException(e.status_code or 502, str(e))

    if order is None:
        raise HTTPException(
            404,
            "No paid order found for this listing yet — it may not have sold, "
            "or the sale is older than the lookback window.",
        )

    # FOR UPDATE taken only now, right before the write — not across the eBay
    # API call above. Global lock order across this codebase's cross-channel
    # paths is always ManualBuild before Product (see cross_channel_guard.py
    # and public_showcase.py's confirm_checkout), to avoid an ABBA deadlock
    # between this route and the storefront-checkout route, which both touch
    # the same ManualBuild/Product pair when a sale is confirmed.
    locked_result = await db.execute(
        select(ManualBuild).where(ManualBuild.id == build_id).with_for_update()
    )
    build = locked_result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    build.ebay_order_id = order.order_id
    build.buyer_name = order.buyer_address.contact_name
    # line_item_id is embedded here (not its own column) since it's only
    # ever needed alongside the address, to push tracking back in
    # book_shipment below.
    build.buyer_address_json = {**order.buyer_address.to_dict(), "line_item_id": order.line_item_id}
    build.sale_price_actual = order.sale_price
    build.status = "sold"
    from app.services.inventory_lifecycle import record_sale
    await record_sale(db, build, order.sale_price)
    build.updated_at = datetime.utcnow()
    await db.flush()

    # This build just sold on eBay — pull any matching storefront listing
    # so the same physical unit can't also sell there. See
    # app/services/cross_channel_guard.py. Still within the ManualBuild lock
    # taken above, then takes the Product lock — ManualBuild-before-Product,
    # matching the global order.
    await withdraw_storefront_for_sold_build(build, db)
    await db.commit()

    return SyncEbayOrderResult(
        ebay_order_id=order.order_id,
        buyer_name=order.buyer_address.contact_name,
        buyer_address=BuyerAddressOut(**order.buyer_address.to_dict()),
        sale_price_actual=order.sale_price,
    )


@router.post("/{build_id}/book-shipment", response_model=BookShipmentResult)
async def book_shipment(build_id: int, body: BookShipmentRequest, db: AsyncSession = Depends(get_db)):
    """Books and pays for a real Parcel2Go shipment using the build's real,
    already-synced buyer address (see sync_ebay_order above), then pushes
    the resulting tracking number to eBay so the buyer sees it.

    This is the one step in the whole shipping flow that spends real money —
    it only runs when explicitly called from the "Book & Pay" button the
    seller clicks after reviewing the quoted price, never automatically."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    if not build.buyer_address_json or not build.ebay_order_id:
        raise HTTPException(400, "Sync the real eBay order first (sync-ebay-order) before booking a shipment.")
    if not build.shipping_damage_cover_confirmed:
        raise HTTPException(
            409,
            "Shipment booking is blocked until separate full-value transit-damage cover is confirmed. "
            "Parcel2Go classifies computers/electricals as protected for loss only.",
        )

    missing = [
        field
        for field in ("package_weight_kg", "package_length_cm", "package_width_cm", "package_height_cm")
        if getattr(build, field) is None
    ]
    if missing:
        raise HTTPException(400, f"Set the build's package dimensions first (missing: {', '.join(missing)}).")

    settings = get_settings()
    buyer_address = BuyerAddress(
        contact_name=build.buyer_address_json.get("contact_name", build.buyer_name or "Unknown"),
        address_line1=build.buyer_address_json.get("address_line1"),
        address_line2=build.buyer_address_json.get("address_line2"),
        city=build.buyer_address_json.get("city"),
        state_or_province=build.buyer_address_json.get("state_or_province"),
        postal_code=build.buyer_address_json.get("postal_code"),
        country_code=build.buyer_address_json.get("country_code", "GB"),
        phone=build.buyer_address_json.get("phone"),
    )
    value_gbp = build.sale_price_actual or build.ebay_price or build.total_cost or 0.0

    try:
        order_id, order_hash = await create_parcel2go_order(
            service_slug=body.service_slug,
            weight_kg=build.package_weight_kg,
            length_cm=build.package_length_cm,
            width_cm=build.package_width_cm,
            height_cm=build.package_height_cm,
            value_gbp=value_gbp,
            buyer_address=buyer_address,
            environment=settings.parcel2go_environment,
        )
        booked = await pay_order_with_prepay(order_id, order_hash, environment=settings.parcel2go_environment)
    except Parcel2GoBookingError as e:
        return BookShipmentResult(success=False, error=str(e))

    # Persist immediately — payment has already happened at this point, so
    # this must be saved even if the eBay push below fails.
    build.parcel2go_order_id = booked.parcel2go_order_id
    build.parcel2go_service_slug = body.service_slug
    build.tracking_number = booked.tracking_number
    build.shipping_label_url = booked.label_url
    build.shipment_booked_at = datetime.utcnow()
    build.updated_at = datetime.utcnow()
    await db.flush()

    if not booked.tracking_number:
        return BookShipmentResult(
            success=True,
            tracking_number=None,
            shipping_label_url=booked.label_url,
            parcel2go_order_id=booked.parcel2go_order_id,
            ebay_marked_shipped=False,
            warning=(
                "Payment succeeded but no tracking number was found in Parcel2Go's response — "
                "check the label manually and enter tracking on eBay yourself. "
                f"Raw response logged for order {booked.parcel2go_order_id}."
            ),
        )

    try:
        # Extract the eBay-side courier name from the offer's original quote
        # is not available here, so use the same service slug's courier via
        # a best-effort split — good enough for eBay's carrier code mapping,
        # which already falls back to "OTHER" on anything unrecognized.
        courier_name = body.service_slug.split("-")[0]
        await mark_order_shipped(
            order_id=build.ebay_order_id,
            line_item_id=build.buyer_address_json.get("line_item_id", ""),
            tracking_number=booked.tracking_number,
            courier_name=courier_name,
            environment=settings.ebay_listing_environment,
        )
    except EbayShippingFulfillmentError as e:
        return BookShipmentResult(
            success=True,
            tracking_number=booked.tracking_number,
            shipping_label_url=booked.label_url,
            parcel2go_order_id=booked.parcel2go_order_id,
            ebay_marked_shipped=False,
            warning=f"Shipment booked and paid, but marking the eBay order as shipped failed: {e}. Enter tracking on eBay manually.",
        )

    return BookShipmentResult(
        success=True,
        tracking_number=booked.tracking_number,
        shipping_label_url=booked.label_url,
        parcel2go_order_id=booked.parcel2go_order_id,
        ebay_marked_shipped=True,
    )


@router.patch("/{build_id}/aspects", response_model=ManualBuildOut)
async def update_aspects(build_id: int, body: UpdateAspectsRequest, db: AsyncSession = Depends(get_db)):
    """Manually edit/correct the generated Item Specifics before listing."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    problems = validate_aspects_for_ebay(body.aspects)
    if problems:
        raise HTTPException(400, "Invalid Item Specifics: " + "; ".join(problems))

    build.generated_aspects = body.aspects
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.put("/{build_id}/evidence-data", response_model=ManualBuildOut)
async def update_evidence_data(build_id: int, body: UpdateEvidenceDataRequest, db: AsyncSession = Depends(get_db)):
    """Stores the structured factual data (JSON) behind the spec card,
    registration plate, or performance card for this build — this is what
    actually gets sent to the LLM for listing generation, as plain text.
    The rendered PNG images (uploaded separately via /photos and
    /photos/branded) are just a visual rendering of this same data for the
    seller's own reference and for the eBay listing photos themselves."""
    if body.kind not in ("spec_card", "registration_plate", "performance_card"):
        raise HTTPException(400, "kind must be 'spec_card', 'registration_plate' or 'performance_card'")

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    evidence = dict(build.evidence_data or {})
    evidence[body.kind] = body.data
    build.evidence_data = evidence
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.patch("/{build_id}/ebay-config", response_model=ManualBuildOut)
async def update_ebay_config(
    build_id: int, body: UpdateEbayListingConfigRequest, db: AsyncSession = Depends(get_db)
):
    """Update eBay listing configuration (condition, price, shipping, offers)."""
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    if body.ebay_condition is not None:
        build.ebay_condition = body.ebay_condition
    if body.ebay_price is not None:
        build.ebay_price = body.ebay_price
    if body.allow_offers is not None:
        build.allow_offers = body.allow_offers
    if body.auto_reject_below_price is not None:
        build.auto_reject_below_price = body.auto_reject_below_price
    if body.auction_start_price is not None:
        build.auction_start_price = body.auction_start_price
    if body.return_days is not None:
        build.return_days = body.return_days
    if body.shipping_method is not None:
        build.shipping_method = body.shipping_method
    if body.shipping_cost is not None:
        build.shipping_cost = body.shipping_cost
    if body.shipping_insurance_cost is not None:
        build.shipping_insurance_cost = max(0.0, body.shipping_insurance_cost)
    if body.packaging_cost is not None:
        build.packaging_cost = max(0.0, body.packaging_cost)
    if body.warranty_reserve_pct is not None:
        build.warranty_reserve_pct = min(25.0, max(0.0, body.warranty_reserve_pct))
    if body.marketplace_fees_actual is not None:
        build.marketplace_fees_actual = max(0.0, body.marketplace_fees_actual)
    if body.promotion_cost_actual is not None:
        build.promotion_cost_actual = max(0.0, body.promotion_cost_actual)
    if body.refund_amount is not None:
        build.refund_amount = max(0.0, body.refund_amount)
    if body.warranty_claim_cost is not None:
        build.warranty_claim_cost = max(0.0, body.warranty_claim_cost)
    if body.handling_time_days is not None:
        build.handling_time_days = body.handling_time_days
    if body.shipping_damage_cover_confirmed is not None:
        build.shipping_damage_cover_confirmed = body.shipping_damage_cover_confirmed
    if body.ships_to_countries is not None:
        build.ships_to_countries = body.ships_to_countries
    if body.domestic_only is not None:
        build.domestic_only = body.domestic_only
    if body.fulfillment_policy_id is not None:
        build.fulfillment_policy_id = body.fulfillment_policy_id
    if body.package_weight_kg is not None:
        build.package_weight_kg = body.package_weight_kg
    if body.package_length_cm is not None:
        build.package_length_cm = body.package_length_cm
    if body.package_width_cm is not None:
        build.package_width_cm = body.package_width_cm
    if body.package_height_cm is not None:
        build.package_height_cm = body.package_height_cm
    # Unlike the fields above, deferred_publish_at must be explicitly
    # clearable (the user cancels a scheduled time), so this checks whether
    # the field was sent at all rather than whether it's non-null.
    if "deferred_publish_at" in body.model_fields_set:
        build.deferred_publish_at = body.deferred_publish_at
    if body.traffic_band is not None:
        build.traffic_band = body.traffic_band
    if body.recreate_price_step_pct is not None:
        build.recreate_price_step_pct = body.recreate_price_step_pct
    if body.markdown_event_opt_in is not None:
        build.markdown_event_opt_in = body.markdown_event_opt_in
    if body.promoted_enabled is not None:
        build.promoted_enabled = body.promoted_enabled
    if body.promoted_ad_rate_pct is not None:
        build.promoted_ad_rate_pct = body.promoted_ad_rate_pct

    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}/ebay-listing", response_model=ManualBuildOut)
async def end_ebay_listing(build_id: int, db: AsyncSession = Depends(get_db)):
    """End the live eBay offer while preserving the build for editing/relisting."""
    import structlog

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.ebay_listing_id:
        raise HTTPException(409, "This build does not have a live eBay listing to end")
    if not build.ebay_sku:
        raise HTTPException(
            409,
            "This listing has no saved eBay SKU, so it cannot be ended safely from FlipFlop",
        )

    listing_id = build.ebay_listing_id
    sku = build.ebay_sku
    settings = get_settings()
    log = structlog.get_logger(__name__)

    try:
        await withdraw_listing_by_sku(sku, environment=settings.ebay_listing_environment)
    except EbayListingWithdrawError as exc:
        log.error(
            "manual_build.ebay_listing_end_failed",
            build_id=build_id,
            listing_id=listing_id,
            sku=sku,
            ebay_status=exc.status_code,
        )
        raise HTTPException(
            502,
            "eBay could not end the listing. Nothing was changed in FlipFlop; please try again.",
        ) from exc

    # Preserve the ended listing ID/SKU as historical evidence. Publishing
    # logic keys off ebay_listing_status, not mere ID presence, so the next
    # publish creates a fresh offer rather than trying to revise this one.
    build.ebay_listing_status = "ended"
    build.ebay_listing_status_checked_at = datetime.utcnow()
    build.ebay_listing_end_reason = "ended_early"
    build.deferred_publish_at = None
    if build.status == "listed":
        build.status = "built"
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    build.ebay_live = False

    log.info(
        "manual_build.ebay_listing_ended",
        build_id=build_id,
        listing_id=listing_id,
        sku=sku,
    )
    return build


@router.post("/{build_id}/post-to-ebay", response_model=PostToEbayResult)
async def post_to_ebay(build_id: int, body: PostToEbayRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    # Persist the seller's asking price as build configuration before making
    # the external eBay request. This keeps the value after reloads and also
    # preserves it when eBay rejects a listing update.
    build.ebay_price = body.price
    build.updated_at = datetime.utcnow()
    await db.flush()

    if not build.generated_title or not build.generated_description:
        raise HTTPException(400, "Generate the listing content before posting to eBay")

    # FAQ choices can be changed after the description was generated. Always
    # refresh the deterministic FAQ block immediately before publication.
    build.generated_description = prepare_ebay_listing_description(
        _description_with_selected_faqs(build.generated_description, build)
    )

    # Do not allow an older generated description to bypass the customer-facing
    # delivery/returns/support wording added to the current listing workflow.
    if "data-flipflop-customer-policy" not in build.generated_description:
        return_period = (
            f"{build.return_days}-day returns" if build.return_days else "No voluntary returns period set"
        )
        policy_html = f"""
<section data-flipflop-customer-policy="true" style="margin-top:24px;padding:20px;border:1px solid #d7dce2;border-radius:12px;background:#f7f9fb;color:#17202a;">
  <h2 style="margin:0 0 12px;font-size:20px;">Delivery, returns &amp; support</h2>
  <p><strong>Dispatch:</strong> Within {build.handling_time_days or 1} working day(s), followed by tracked delivery.</p>
  <p><strong>Returns:</strong> {return_period}. The buyer pays return postage for a change of mind; flipflop pays reasonable return postage if the PC is faulty, damaged or misdescribed.</p>
  <p><strong>Your rights:</strong> UK statutory consumer rights are not affected. Manufacturer warranties are passed on where transferable.</p>
  <p><strong>Support:</strong> Direct setup and after-sales support is available from flipflop.</p>
</section>
"""
        build.generated_description = prepare_ebay_listing_description(
            build.generated_description + policy_html
        )
        build.updated_at = datetime.utcnow()
        await db.flush()

    # Builds generated before cardinality validation can still contain arrays
    # such as Brand=[AMD, NVIDIA, Corsair] and Storage Type=[SSD, HDD]. Repair
    # those deterministic legacy cases and persist them before validation and
    # submission so the user does not have to re-enter otherwise valid data.
    repaired_aspects = repair_legacy_aspect_cardinality(build.generated_aspects or {})
    if repaired_aspects != (build.generated_aspects or {}):
        build.generated_aspects = repaired_aspects
        build.updated_at = datetime.utcnow()
        await db.flush()

    missing_required = [a for a in ("Brand", "Type") if not (build.generated_aspects or {}).get(a)]
    if missing_required:
        raise HTTPException(
            400,
            f"Item Specifics are incomplete (missing: {', '.join(missing_required)}). "
            "Generate or fill in the listing's Specifics section before posting to eBay.",
        )
    # Defensive re-check even though update_aspects now validates on save —
    # catches aspects written before that validation existed (like the
    # over-length "Connectivity" free-text value that first surfaced this
    # bug), turning what would be a slow eBay API rejection into an
    # immediate, fixable local error.
    aspect_problems = validate_aspects_for_ebay(build.generated_aspects or {})
    if aspect_problems:
        raise HTTPException(
            400,
            "Item Specifics have invalid values — fix these in the Specifics section before posting: "
            + "; ".join(aspect_problems),
        )

    # Get image URLs from build photos (already public URLs)
    image_urls = []
    if build.photos:
        for photo in build.photos:
            # Photo is stored as {"url": "https://theflipflop.shop/media/...", "kind": "photo"}
            photo_url = photo.get("url") if isinstance(photo, dict) else photo
            if photo_url:
                image_urls.append(photo_url)

    if not image_urls:
        raise HTTPException(400, "Upload at least one photo before listing on eBay")

    # Listing/publishing target (sandbox vs production) is driven by
    # EBAY_LISTING_ENVIRONMENT — credentials, token, and business policies
    # all switch together with it. Token is auto-renewed via the stored
    # refresh token when possible, falling back to the static one.
    from app.services.ebay_token_manager import get_valid_ebay_access_token

    settings = get_settings()
    listing_environment = settings.ebay_listing_environment

    try:
        oauth_token = await get_valid_ebay_access_token(listing_environment)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if listing_environment == "production":
        payment_policy_id = settings.ebay_production_payment_policy_id
        return_policy_id = settings.ebay_production_return_policy_id
        fulfillment_policy_id = settings.ebay_production_fulfillment_policy_id
    else:
        payment_policy_id = settings.ebay_sandbox_payment_policy_id
        return_policy_id = settings.ebay_sandbox_return_policy_id
        fulfillment_policy_id = settings.ebay_sandbox_fulfillment_policy_id

    # Per-build shipping-destination choice (picked from the seller's real
    # eBay fulfillment policies via the Shipping & Delivery section) wins
    # over the single global default every other listing falls back to.
    if build.fulfillment_policy_id:
        fulfillment_policy_id = build.fulfillment_policy_id

    try:
        # Reconcile before choosing create vs revise. An ID by itself only
        # proves this build was listed historically; it does not prove that
        # the offer is still live.
        if build.ebay_listing_id:
            from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
            remote_state = await reconcile_manual_build_listing(
                build,
                db,
                force=True,
                access_token=oauth_token,
                environment=listing_environment,
            )
        else:
            remote_state = "never_listed"
        if remote_state == "unknown":
            raise HTTPException(
                503,
                "eBay listing status could not be verified. No listing was created or updated; retry when eBay is reachable.",
            )
        is_relisting = remote_state == "active"

        if is_relisting:
            # Update existing eBay listing
            result = await post_flip_to_ebay(
                title=build.generated_title,
                description=build.generated_description,
                price=body.price,
                image_urls=image_urls,
                access_token=oauth_token,
                environment=listing_environment,
                condition=body.condition,
                payment_policy_id=payment_policy_id,
                return_policy_id=return_policy_id,
                fulfillment_policy_id=fulfillment_policy_id,
                aspects=build.generated_aspects or {},
                listing_id=build.ebay_listing_id,  # Pass existing ID to update
                sku=build.ebay_sku,
            )
        else:
            # Create new eBay listing
            result = await post_flip_to_ebay(
                title=build.generated_title,
                description=build.generated_description,
                price=body.price,
                image_urls=image_urls,
                access_token=oauth_token,
                environment=listing_environment,
                condition=body.condition,
                payment_policy_id=payment_policy_id,
                return_policy_id=return_policy_id,
                fulfillment_policy_id=fulfillment_policy_id,
                aspects=build.generated_aspects or {},
            )

        if result["success"]:
            from app.services.traffic_bands import jittered_recreate_slot, DEFAULT_BAND

            build.ebay_listing_id = result["listing_id"]
            build.ebay_listing_url = result["url"]
            build.ebay_sku = result.get("sku")
            build.status = "listed"
            build.ebay_listing_status = "active"
            build.ebay_listing_status_checked_at = datetime.utcnow()
            build.ebay_listing_end_reason = None
            build.deferred_publish_at = None
            build.updated_at = datetime.utcnow()
            if not build.ebay_price:
                build.ebay_price = body.price
            if build.listed_at is None:
                # Rows 1/2/5/6/9: start the recreate/relist cycle clock the
                # first time this build actually goes live, whichever path
                # got it there (manual "List on eBay" here, or the deferred
                # scheduler in manual_build_scheduler.py).
                build.listed_at = datetime.utcnow()
                build.next_recreate_at = jittered_recreate_slot(
                    build.traffic_band or DEFAULT_BAND, datetime.utcnow(),
                )

            # Row 40: promote automatically if opted in — a failure here
            # doesn't undo the listing itself, just logs.
            if build.promoted_enabled:
                try:
                    from app.services.ebay_marketing import set_promoted_ad

                    rate = build.promoted_ad_rate_pct
                    if rate is None:
                        suggestion = pricing_engine.suggest_promoted_ad_rate(
                            estimated_profit=body.price - (build.total_cost or 0),
                            total_cost=build.total_cost or 0,
                        )
                        rate = suggestion["suggested_ad_rate_pct"] * 100 if not suggestion["too_thin_to_promote"] else None
                    if rate is not None:
                        await set_promoted_ad(build.ebay_listing_id, rate, oauth_token, listing_environment)
                except Exception as exc:
                    log.warning("manual_builds.promote_failed", build_id=build.id, error=str(exc))

            await db.flush()
            action = "updated" if is_relisting else "posted"
            return PostToEbayResult(success=True, listing_id=result["listing_id"], url=result["url"], action=action)

        return PostToEbayResult(success=False, error=result.get("error", f"Failed to {'update' if is_relisting else 'post'} listing"))
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        return PostToEbayResult(success=False, error=f"Error {'updating' if locals().get('is_relisting') else 'posting'} to eBay: {error_msg}")


@router.post("/{build_id}/photos", response_model=ManualBuildOut)
async def upload_photos(
    build_id: int,
    files: list[UploadFile] = File(...),
    kind: str = Form("photo"),
    db: AsyncSession = Depends(get_db),
):
    """kind defaults to "photo" (regular listing photos) but also accepts
    "performance_card" — the build-specific benchmark/performance renders
    uploaded from the build detail page's Performance Card section. Tagging
    them lets generate-listing find exactly this build's performance
    evidence rather than relying on any shared/global file."""
    if kind not in ("photo", "performance_card"):
        raise HTTPException(400, "kind must be 'photo' or 'performance_card'")

    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    build_dir = _UPLOADS_ROOT / str(build_id)
    build_dir.mkdir(parents=True, exist_ok=True)

    photos = list(build.photos or [])
    _PUBLIC_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    uploaded_urls = []
    for file in files:
        content_type = file.content_type or "image/jpeg"
        if content_type not in _IMAGE_TYPES:
            raise HTTPException(415, f"Unsupported image type: {content_type}. Use JPEG, PNG or WebP.")
        image_bytes = await file.read()
        if len(image_bytes) > _MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image too large (max 15 MB)")

        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]
        filename = f"{uuid.uuid4().hex}.{ext}"

        # Save to local uploads directory
        (build_dir / filename).write_bytes(image_bytes)

        # Also copy to public FlipFlop.shop media directory for eBay
        public_path = _PUBLIC_MEDIA_ROOT / filename
        public_path.write_bytes(image_bytes)

        # Push to the live flipflop-shop VPS so the public URL actually resolves
        await sync_to_public_media(public_path)

        # Use public URL for eBay listings
        public_url = f"https://theflipflop.shop/media/{filename}"
        photos.append({"url": public_url, "kind": kind})
        uploaded_urls.append(public_url)

    build.photos = photos
    if kind == "photo" and not build.hero_photo_url and uploaded_urls:
        build.hero_photo_url = uploaded_urls[0]
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/photos/branded", response_model=ManualBuildOut)
async def upload_branded_asset(
    build_id: int,
    kind: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Store a client-rendered branded card (spec card / registration plate)."""
    if kind not in ("spec_card", "registration_plate"):
        raise HTTPException(400, "kind must be 'spec_card' or 'registration_plate'")
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    build_dir = _UPLOADS_ROOT / str(build_id)
    build_dir.mkdir(parents=True, exist_ok=True)
    _PUBLIC_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    image_bytes = await file.read()
    filename = f"{kind}-{uuid.uuid4().hex}.png"
    (build_dir / filename).write_bytes(image_bytes)
    public_path = _PUBLIC_MEDIA_ROOT / filename
    public_path.write_bytes(image_bytes)
    await sync_to_public_media(public_path)

    photos = [p for p in (build.photos or []) if p.get("kind") != kind]
    photos.append({"url": f"https://theflipflop.shop/media/{filename}", "kind": kind})
    build.photos = photos
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/model-3d", response_model=ManualBuildOut)
async def upload_build_3d_model(
    build_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Store one self-contained GLB for the completed-build web viewer."""
    if not (file.filename or "").lower().endswith(".glb"):
        raise HTTPException(400, "Upload a self-contained .glb model")
    model_bytes = await file.read()
    if not model_bytes:
        raise HTTPException(400, "The GLB file is empty")
    if len(model_bytes) > 100 * 1024 * 1024:
        raise HTTPException(413, "The GLB must be 100 MB or smaller")
    # Binary glTF begins with the ASCII magic bytes 'glTF'. This rejects a
    # renamed ZIP/OBJ before it can reach the public storefront.
    if model_bytes[:4] != b"glTF":
        raise HTTPException(400, "The uploaded file is not a valid binary GLB")

    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    _PUBLIC_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"build-{build_id}-3d-{uuid.uuid4().hex}.glb"
    public_path = _PUBLIC_MEDIA_ROOT / filename
    public_path.write_bytes(model_bytes)
    await sync_to_public_media(public_path)
    build.model_3d_url = f"https://theflipflop.shop/media/{filename}"
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}/photos", response_model=ManualBuildOut)
async def remove_photo(build_id: int, body: RemovePhotoRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    photos = [p for p in (build.photos or []) if p.get("url") != body.url]
    build.photos = photos
    if build.hero_photo_url == body.url:
        build.hero_photo_url = photos[0]["url"] if photos else None
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.put("/{build_id}/photos/order", response_model=ManualBuildOut)
async def reorder_photos(build_id: int, body: ReorderPhotosRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    existing = list(build.photos or [])
    by_url = {p["url"]: p for p in existing if p.get("kind") == "photo"}
    if set(body.urls) != set(by_url.keys()):
        raise HTTPException(400, "urls must be exactly the build's current photo URLs")

    non_photo = [p for p in existing if p.get("kind") != "photo"]
    reordered = [by_url[u] for u in body.urls]
    build.photos = reordered + non_photo
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/photos/hero", response_model=ManualBuildOut)
async def set_hero_photo(build_id: int, body: SetHeroPhotoRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not any(p.get("url") == body.url for p in (build.photos or [])):
        raise HTTPException(400, "That photo isn't attached to this build")

    build.hero_photo_url = body.url
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/list-on-storefront", response_model=ListOnStorefrontResult)
async def list_on_storefront(
    build_id: int,
    body: ListOnStorefrontRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish this build to the FlipFlop.shop pre-built showcase — the first
    code path in this codebase that actually creates a Product row (Build →
    Product has been a schema-only relationship until now).
    """
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if build.status not in ("built", "listed", "sold"):
        raise HTTPException(400, "Mark this build as built before listing it on the storefront")
    if not build.hero_photo_url:
        raise HTTPException(400, "Choose a hero photo before listing on the storefront")
    if not build.generated_title or not build.generated_description:
        raise HTTPException(400, "Generate the listing title/description before listing on the storefront")

    if build.storefront_product_id:
        product_result = await db.execute(select(Product).where(Product.id == build.storefront_product_id))
        product = product_result.scalar_one_or_none()
        if product:
            product.price = body.price
            product.status = ProductStatus.LISTED
            product.hero_photo_url = build.hero_photo_url
            product.title = build.generated_title
            product.description = build.generated_description
            product.model_3d_url = build.model_3d_url
            product.selected_faqs = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
            product.fulfilment_type = "prebuilt"
            product.handling_min_days = 1
            product.handling_max_days = 1
            product.delivery_min_days = 1
            product.delivery_max_days = 2
            await db.flush()
            return ListOnStorefrontResult(product_id=product.id, build_id=product.build_id, storefront_url=f"/ready-to-ship/{product.id}")

    orchestration_build = Build(
        build_type=BuildType.PREBUILT,
        manual_build_id=build.id,
        spec_json=build.components,
        status=BuildStatus.FINALISED,
    )
    db.add(orchestration_build)
    await db.flush()
    await db.refresh(orchestration_build)

    product = Product(
        product_type=ProductType.PREBUILT,
        build_id=orchestration_build.id,
        title=build.generated_title,
        description=build.generated_description,
        price=body.price,
        status=ProductStatus.LISTED,
        hero_photo_url=build.hero_photo_url,
        model_3d_url=build.model_3d_url,
        selected_faqs=selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides),
        fulfilment_type="prebuilt",
        handling_min_days=1,
        handling_max_days=1,
        delivery_min_days=1,
        delivery_max_days=2,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    build.storefront_product_id = product.id
    build.updated_at = datetime.utcnow()
    await db.flush()

    return ListOnStorefrontResult(product_id=product.id, build_id=orchestration_build.id, storefront_url=f"/ready-to-ship/{product.id}")
