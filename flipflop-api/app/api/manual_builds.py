import json
import re
import uuid
import os
from pathlib import Path
from datetime import datetime
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.manual_build import ManualBuild
from app.models.build import Build, BuildType, BuildStatus
from app.models.product import Product, ProductType, ProductStatus
from app.schemas.manual_build import (
    ManualBuildCreate, ManualBuildPatch, ManualBuildOut, ManualBuildSummary,
    EvaluationResult, EvaluationSuggestion, GenerateListingResult,
    PostToEbayRequest, PostToEbayResult, SetHeroPhotoRequest, RemovePhotoRequest,
    ListOnStorefrontRequest, ListOnStorefrontResult, ReorderPhotosRequest,
    UpdateAspectsRequest, UpdateEbayListingConfigRequest, FulfillmentPolicyOut,
    CourierQuoteOut, SyncEbayOrderResult, BuyerAddressOut, BookShipmentRequest,
    BookShipmentResult,
)
from app.services import ai_service
from app.services.ebay_listing_poster import post_flip_to_ebay
from app.services.ebay_specifics_generator import generate_item_specifics, validate_aspects_for_ebay
from app.services.ebay_fulfillment_policies import (
    list_fulfillment_policies,
    EbayFulfillmentPoliciesError,
)
from app.services.parcel2go_courier import get_cheapest_tracked_quote, Parcel2GoError
from app.services.ebay_order_sync import find_order_for_listing, EbayOrderSyncError, BuyerAddress
from app.services.parcel2go_booking import (
    create_order as create_parcel2go_order,
    pay_order_with_prepay,
    Parcel2GoBookingError,
)
from app.services.ebay_shipping_fulfillment import mark_order_shipped, EbayShippingFulfillmentError
from app.services.cross_channel_guard import withdraw_storefront_for_sold_build
from app.services.media_sync import sync_to_public_media
from app.config import get_settings
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/manual-builds", tags=["manual-builds"], dependencies=[Depends(get_current_admin)])

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB
_UPLOADS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "manual_builds"
_PUBLIC_MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "FlipFlop.shop" / "public" / "media"
_SELLING_PRINCIPLES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "selling_principles.md"
_EBAY_LISTING_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ebay_listing_system_prompt.md"

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


@router.post("/", response_model=ManualBuildOut, status_code=201)
async def create_build(body: ManualBuildCreate, db: AsyncSession = Depends(get_db)):
    build = ManualBuild(name=body.name, components=[], total_cost=None)
    db.add(build)
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/", response_model=list[ManualBuildSummary])
async def list_builds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManualBuild).order_by(ManualBuild.updated_at.desc())
    )
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


@router.get("/{build_id}", response_model=ManualBuildOut)
async def get_build(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")

    # Channel-live status for the "which sites is this actually purchasable
    # on right now" badges — computed here rather than stored, since it can
    # change independently (cross-channel-guard withdrawal, a manual eBay
    # end-listing, etc.) and must always reflect current reality, not
    # whatever was true when the build was last written to.
    build.ebay_live = bool(build.ebay_listing_id) and build.status == "listed"
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


@router.delete("/{build_id}", status_code=204)
async def delete_build(build_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    await db.delete(build)


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
    await db.flush()
    await db.refresh(build)
    return build


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

    selling_principles = _load_selling_principles()
    principles_block = f"\n\nFollow these selling principles when writing the title and description:\n\n{selling_principles}\n" if selling_principles else ""

    aspect_names = ", ".join(_EBAY_CATEGORY_179_ASPECTS)

    prompt = f"""Generate STUNNING, PREMIUM eBay listing content for this second-hand PC build for the UK market. This description must STAND OUT and DAZZLE buyers. Here are its components:

{component_text}
{principles_block}

DESIGN BRIEF: Create a LUXURY listing that makes buyers say "WOW" — premium feel, flawless execution, professional excellence. USE FLIPFLOP BRAND COLORS THROUGHOUT.

TECHNICAL REQUIREMENTS:
1. Pure HTML + inline styles ONLY (no <style> blocks — eBay strips them)
2. Semantic tags: <h1>, <h2>, <h3>, <p>, <div>, <ul>, <li>, <strong>, <em>, <hr>
3. NO markdown, NO asterisks, NO casual language
4. INCLUDE FlipFlop logo in hero section if available

STUNNING DESIGN SYSTEM:
Color Palette (FlipFlop brand identity):
- PRIMARY: #0066FF (vibrant FlipFlop blue — use for headings, borders, sections)
- ACCENT: #FF6600 (warm FlipFlop orange — use for highlights, premium specs, CTAs)
- SUCCESS: #28A745 (confident green for "TESTED" badges)
- DARK: #1a1a1a (rich black for contrast)
- LIGHT: #F5F5F5 (clean white)

Visual Hierarchy & Effects:
1. HERO SECTION (top) — Use FlipFlop brand gradient:
   <div style="background:linear-gradient(135deg, #0066FF 0%, #FF6600 100%);color:white;padding:30px;border-radius:8px;text-align:center;margin-bottom:20px;">
   - FlipFlop logo or brand name at top (if available)
   - Main headline: Large, bold, white text
   - Tagline: Professional positioning statement
   - Use padding and centered alignment for impact

2. FLIPFLOP LOGO PLACEMENT (Hero):
   Include the FlipFlop logo at the top-right or center of the hero section. Use these logos:
   - Recommended (glow effect): https://theflipflop.shop/media/flipflop-glow-black-with-full-glow.png
   - Alternative (simple): https://theflipflop.shop/media/logo_simple.png
   - Additional: https://theflipflop.shop/media/logo5.png
   Format: <img src="https://theflipflop.shop/media/flipflop-glow-black-with-full-glow.png" style="max-height:60px;margin-bottom:15px;"/>

3. FEATURED IMAGE AREA:
   <p style="text-align:center;margin:30px 0;">[PRODUCT IMAGES WILL BE INSERTED HERE - CENTER ALIGNED]</p>

4. KEY HIGHLIGHTS SECTION:
   - 3-4 major selling points in a visually distinct box
   - Use background-color:#F5F5F5 with padding for visual separation
   - Use <strong> with color:#0066FF for key stats
   - Highlight premium points with color:#FF6600
   - Format: "▸ Benefit statement with specs"

5. SPECIFICATIONS SECTION:
   - Organize by component category (CPU, GPU, RAM, Storage, Motherboard, Power, Cooling)
   - Each spec in a clean, scannable list format
   - Use <strong> tags with strategic color changes (#0066FF for main, #FF6600 for premium)
   - Highlight premium/high-end components with color:#FF6600 (FlipFlop orange)
   - Use borders (color:#0066FF) to separate premium specs from standard ones

5. CONDITION & TESTING SECTION:
   - Bold, centered statement with color:#28A745
   - "✓ FULLY TESTED & VERIFIED" in large, confident text
   - Add details about testing process

6. FLIPFLOP PREMIUM BADGE:
   - Create a visual "badge" effect using FlipFlop brand colors:
   <div style="background:linear-gradient(135deg, #FF6600 0%, #0066FF 100%);color:white;padding:15px;margin:20px 0;border-left:4px solid #FF6600;font-weight:bold;text-align:center;">
   - FlipFlop branding
   - Trust messaging
   - Quality guarantee
   - Support statement

7. BENEFITS FOR BUYER TYPE:
   - Section explaining why this machine is PERFECT for their needs
   - Use #0066FF accents for section headers
   - Use #FF6600 for highlighted benefits

8. SHIPPING & LOGISTICS:
   - Clean, professional formatting with #0066FF accents
   - Highlight speed and reliability in #FF6600

9. FINAL CALL-TO-ACTION:
   - Bold, centered, memorable using FlipFlop colors
   - Use gradient: background linear-gradient(135deg, #FF6600 0%, #0066FF 100%)
   - Make it impossible to miss
   - Example: Large bold white text in FlipFlop gradient box

STYLING TECHNIQUES TO MAXIMIZE IMPACT:
- Use padding/margin generously (20-30px) for breathing room
- Center-align headlines and important statements
- Use left borders (4px) in #0066FF to highlight premium specs, #FF6600 for ultra-premium
- Use background colors to create visual "cards" or sections
- Vary font sizes significantly for hierarchy (use inline style="font-size:18px" for emphasis)
- Use line-height:1.8 for body text (easier to read, more premium feel)
- Bold premium/high-end components with #FF6600 (FlipFlop orange)
- Create visual separation between sections with <hr style="border-color:#0066FF;margin:20px 0;">
- Use FlipFlop brand gradient (linear-gradient(135deg, #0066FF 0%, #FF6600 100%)) for hero sections and CTAs
- Every section should feel connected to the FlipFlop brand identity

TONE:
- Confident, not pushy
- Premium positioning throughout
- Professional, sophisticated language
- Every section must feel intentional and valuable
- Make the reader FEEL the quality

STRUCTURE:
1. Hero section with striking headline
2. Origin story / About FlipFlop (NEW):
   - Brief paragraph explaining: "I'm an experienced software engineer who has built countless high-performance PCs for friends and family over the years. Those builds became legendary for quality and performance. Now I'm turning that passion into FlipFlop — a startup dedicated to crafting and delivering premium custom-built PCs to discerning buyers who demand the very best."
   - This builds credibility and differentiates from typical resellers
   - Keep it authentic but professional
3. [IMAGES PLACEHOLDER]
4. Key highlights (visually distinct)
5. Detailed specifications (well-organized)
6. Condition & testing assurance
7. FlipFlop premium badge & trust messaging
8. Why this machine is perfect for the buyer
9. Shipping details
10. Bold, memorable call-to-action

Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "titles": ["Premium title 1", "Premium title 2", "Premium title 3"],
  "description": "<div style=\\"background:linear-gradient(135deg, #0066FF 0%, #FF6600 100%);color:white;padding:30px;border-radius:8px;text-align:center;margin-bottom:20px;\\"><p style=\\"margin:0 0 15px 0;font-size:12px;font-weight:bold;letter-spacing:2px;\\">FLIPFLOP PREMIUM BUILD</p><h1 style=\\"margin:0;font-size:28px;font-weight:900;\\">Premium Gaming PC - Expertly Built</h1><p style=\\"margin:10px 0 0 0;font-size:14px;\\">Handcrafted by an experienced software engineer</p></div><p style=\\"background-color:#F5F5F5;padding:20px;border-left:4px solid #FF6600;margin:20px 0;line-height:1.8;\\"><strong style=\\"color:#0066FF;\\">About FlipFlop:</strong> I'm an experienced software engineer who has built countless high-performance PCs for friends and family over the years. Those builds became legendary for quality, reliability, and raw performance. Now I'm turning that passion into <strong style=\\"color:#FF6600;\\">FlipFlop</strong> — a startup dedicated to crafting and delivering premium custom-built systems to discerning buyers who demand excellence.</p><p style=\\"text-align:center;margin:30px 0;\\\">[FLIPFLOP LOGO AND PRODUCT IMAGES WILL BE INSERTED HERE]</p><h2 style=\\"color:#0066FF;margin-top:30px;\\">Premium Specifications</h2><p style=\\"border-left:4px solid #0066FF;padding-left:15px;margin:15px 0;\\">Every component selected for performance and quality. <span style=\\"color:#FF6600;font-weight:bold;\\">Premium parts highlighted in orange.</span></p><div style=\\"background-color:#F5F5F5;padding:20px;margin:20px 0;border-radius:8px;border-left:4px solid #FF6600;\\\">[REST OF DESCRIPTION CONTINUES WITH SPECS, HIGHLIGHTS, FLIPFLOP BADGE, CTA...]</div>",
  "aspects": {{...}}
}}

Also generate eBay Item Specifics ("aspects") for category 179 (PC Desktops
& All-in-Ones). Fill in every aspect below that genuinely applies to a
desktop tower, inferring values from the components listed above (e.g.
"Processor" from the CPU component, "GPU" from the graphics card, "RAM
Size" from the memory component, "Storage Type"/"SSD Capacity" from the
storage component, "Form Factor" from the case). Use "Not Included" or a
reasonable default only when a field is genuinely unknown — never leave an
applicable field blank. Omit only aspects that don't apply to a desktop
tower at all (e.g. "Screen Size", "Unit Quantity", "Unit Type").

Available aspects: {aspect_names}

Respond with ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "titles": [
    "Title option 1 (max 80 chars, keyword-rich, professional)",
    "Title option 2 (max 80 chars, different positioning)",
    "Title option 3 (max 80 chars, alternative focus)"
  ],
  "description": "<p>Opening hook about performance and quality.</p><p>[IMAGES WILL BE INSERTED HERE]</p><h2 style=\\"color:#0066cc\\">Premium Specifications</h2><ul><li><strong>CPU:</strong> [Component]</li><li><strong>GPU:</strong> [Component]</li></ul><h2 style=\\"color:#0066cc\\">Condition & Testing</h2><p><strong style=\\"color:#16a34a\\">FULLY TESTED</strong> and ready for immediate use.</p><p>Backed by FlipFlop's quality guarantee. Ships within 1-2 business days.</p><p style=\\"color:#0066cc\\"><strong>Ready to experience premium PC performance? Bid now!</strong></p>",
  "aspects": {{
    "Brand": "FlipFlop",
    "Type": "Desktop",
    "Processor": "...",
    "GPU": "...",
    "RAM Size": "...",
    "...": "one value per applicable aspect from the list above"
  }}
}}"""

    response_text, _model = await ai_service.chat(prompt, history=[])
    if _model == "none":
        raise HTTPException(503, response_text)

    raw = response_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise HTTPException(502, f"LLM returned unparseable response: {raw[:200]}")
        data = json.loads(match.group())

    titles = data.get("titles", [])
    description = data.get("description", "")
    aspects = data.get("aspects", {})
    # eBay's aspects format is {name: [values]} — normalize single strings to lists.
    normalized_aspects = {
        k: (v if isinstance(v, list) else [str(v)])
        for k, v in aspects.items()
        if v not in (None, "", [])
    }
    build.generated_aspects = normalized_aspects

    if titles:
        build.generated_title = titles[0][:80]
    build.generated_description = description
    build.updated_at = datetime.utcnow()
    await db.flush()

    return GenerateListingResult(titles=titles, description=description, aspects=normalized_aspects)


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


@router.post("/{build_id}/courier-quote", response_model=CourierQuoteOut)
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
        quote = await get_cheapest_tracked_quote(
            weight_kg=build.package_weight_kg,
            length_cm=build.package_length_cm,
            width_cm=build.package_width_cm,
            height_cm=build.package_height_cm,
            value_gbp=value_gbp,
            delivery_country=resolved_country,
        )
    except Parcel2GoError as e:
        raise HTTPException(e.status_code or 502, str(e))

    if quote is None:
        raise HTTPException(404, "No tracked courier service found for this destination/parcel size")

    return CourierQuoteOut(
        courier_name=quote.courier_name,
        service_name=quote.service_name,
        price_gbp=quote.price_gbp,
        tracked=quote.tracked,
        estimated_days=quote.estimated_days,
        service_slug=quote.service_slug,
    )


@router.post("/{build_id}/sync-ebay-order", response_model=SyncEbayOrderResult)
async def sync_ebay_order(build_id: int, db: AsyncSession = Depends(get_db)):
    """Fetches this build's real eBay order — buyer name, actual delivery
    address, actual sale price — once it's sold. This data only exists
    after a real buyer has paid; it's never available at listing time.
    Requires ebay_listing_id to already be set (i.e. the build was actually
    posted to eBay). Safe to call again later — it just re-fetches and
    overwrites with the current order state."""
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

    build.ebay_order_id = order.order_id
    build.buyer_name = order.buyer_address.contact_name
    # line_item_id is embedded here (not its own column) since it's only
    # ever needed alongside the address, to push tracking back in
    # book_shipment below.
    build.buyer_address_json = {**order.buyer_address.to_dict(), "line_item_id": order.line_item_id}
    build.sale_price_actual = order.sale_price
    build.status = "sold"
    build.updated_at = datetime.utcnow()
    await db.flush()

    # This build just sold on eBay — pull any matching storefront listing
    # so the same physical unit can't also sell there. See
    # app/services/cross_channel_guard.py.
    await withdraw_storefront_for_sold_build(build, db)

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
    if body.handling_time_days is not None:
        build.handling_time_days = body.handling_time_days
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

    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.post("/{build_id}/post-to-ebay", response_model=PostToEbayResult)
async def post_to_ebay(build_id: int, body: PostToEbayRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.generated_title or not build.generated_description:
        raise HTTPException(400, "Generate the listing content before posting to eBay")
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
            build.ebay_listing_id = result["listing_id"]
            build.ebay_listing_url = result["url"]
            build.ebay_sku = result.get("sku")
            build.status = "listed"
            build.deferred_publish_at = None
            build.updated_at = datetime.utcnow()
            await db.flush()
            return PostToEbayResult(success=True, listing_id=result["listing_id"], url=result["url"])

        return PostToEbayResult(success=False, error=result.get("error", "Failed to post listing"))
    except Exception as e:
        error_msg = str(e)
        return PostToEbayResult(success=False, error=f"Error posting to eBay: {error_msg}")


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
            await db.flush()
            return ListOnStorefrontResult(product_id=product.id, build_id=product.build_id, storefront_url=f"/builds/{product.id}")

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
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    build.storefront_product_id = product.id
    build.updated_at = datetime.utcnow()
    await db.flush()

    return ListOnStorefrontResult(product_id=product.id, build_id=orchestration_build.id, storefront_url=f"/builds/{product.id}")
