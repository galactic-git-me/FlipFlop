"""PC Case sourcing and 3D model management endpoints."""
from datetime import datetime
import os
import re
from urllib.parse import quote_plus
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
import httpx
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.case import Case
from app.models.catalogue import CaseCatalogue
from app.models.listing import Listing
from app.services.browser_pool import managed_playwright
from app.models.gem_radar_intelligence import PreferredComponent
from app.services.media_sync import sync_to_public_media

router = APIRouter(prefix="/cases", tags=["cases"])

SOURCING_STAGES = (
    "manufacturer_3d",
    "third_party_3d",
    "product_images",
    "youtube_video",
    "meshy_generation",
    "validation",
)

CASE_MESHY_PHOTO_REQUIREMENTS = (
    "chassis_empty",
    "included_rgb_fans_installed",
    "rgb_illuminated",
    "no_text_overlay",
    "no_dimension_overlay",
    "no_exploded_view",
    "same_chassis_configuration",
)

CASE_REFERENCE_UPLOAD_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
CASE_REFERENCE_UPLOAD_LIMIT = 15 * 1024 * 1024
CASE_REFERENCE_PUBLIC_ROOT = Path(__file__).resolve().parents[3].parent / "FlipFlop.shop" / "public" / "media"
CASE_REFERENCE_PUBLIC_URL = "https://theflipflop.shop/media"


_PREFERENCE_NOISE_WORDS = {"case", "chassis", "tower", "mid", "full", "pc", "computer", "gaming", "iridescent"}


def _is_preferred_case(case: Case, preferred_names: list[str]) -> bool:
    case_tokens = {token for token in "".join(char.lower() if char.isalnum() else " " for char in case.name).split() if token not in _PREFERENCE_NOISE_WORDS}
    for preferred_name in preferred_names:
        preferred_tokens = {token for token in "".join(char.lower() if char.isalnum() else " " for char in preferred_name).split() if token not in _PREFERENCE_NOISE_WORDS}
        if preferred_tokens and preferred_tokens.issubset(case_tokens):
            return True
    return False


async def _preferred_case_names(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(PreferredComponent.component_key).where(
            PreferredComponent.component_slot == "case",
            PreferredComponent.status == "preferred",
        )
    )
    return list(result.scalars().all())


def _priority_payload(case: Case, preferred_names: list[str] | None = None) -> dict:
    return {
        "id": case.id,
        "name": case.name,
        "brand": case.brand,
        "model": case.model,
        "price": case.price_new or case.price or 0,
        "rrp": case.rrp,
        "source_site": case.source_site,
        "source_url": case.source_url,
        "image_url": case.image_url,
        "bestseller_rank": case.bestseller_rank,
        "priority_3d_rank": case.priority_3d_rank,
        "priority_3d_batch": case.priority_3d_batch,
        "priority_3d_frozen_at": case.priority_3d_frozen_at.isoformat() if case.priority_3d_frozen_at else None,
        "rating": case.rating,
        "review_count": case.review_count,
        "sales_velocity": case.sales_velocity,
        "keywords": case.keywords or [],
        "form_factors": case.form_factors or [],
        "is_preferred": _is_preferred_case(case, preferred_names or []),
        "has_3d_model": bool(case.has_3d_model),
        "model_3d_url": case.model_3d_url,
        "status": case.status,
        "sourcing_3d_evidence": case.sourcing_3d_evidence or {},
    }


@router.post("/priority-for-3d/freeze")
async def freeze_top_30_3d_campaign(db: AsyncSession = Depends(get_db)):
    """Freeze the current top 30 into three stable ten-case work batches."""
    from sqlalchemy import case as sql_case

    existing = (
        await db.execute(
            select(Case)
            .where(Case.priority_3d_rank.isnot(None), ~Case.name.ilike("%raspberry%"))
            .order_by(Case.priority_3d_rank)
        )
    ).scalars().all()
    preferred_names = await _preferred_case_names(db)
    if existing:
        return {"frozen": False, "reason": "campaign_already_frozen", "cases": [_priority_payload(case, preferred_names) for case in existing]}

    ranked = (
        await db.execute(
            select(Case)
            .where(Case.has_3d_model == False, ~Case.name.ilike("%raspberry%"))  # noqa: E712
            .order_by(
                Case.bestseller_rank.asc().nullslast(),
                sql_case((Case.source_site == "Amazon", 0), else_=1),
                Case.price.asc(),
                Case.id,
            )
            .limit(30)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    frozen_at = datetime.utcnow()
    for index, case in enumerate(ranked, start=1):
        case.priority_3d_rank = index
        case.priority_3d_batch = ((index - 1) // 10) + 1
        case.priority_3d_frozen_at = frozen_at
        case.sourcing_3d_evidence = {
            "schema_version": 1,
            "stages": {stage: {"status": "not_started", "attempts": []} for stage in SOURCING_STAGES},
        }
    await db.commit()
    return {"frozen": True, "cases": [_priority_payload(case, preferred_names) for case in ranked]}


class SourcingEvidencePatch(BaseModel):
    stage: str
    status: str = Field(pattern="^(not_started|searching|found|not_found|blocked|complete)$")
    attempt: dict | None = None


class CaseReferenceImage(BaseModel):
    url: HttpUrl
    source: str = Field(pattern="^(amazon|manufacturer|google|retailer|manual)$")
    source_page: HttpUrl | None = None
    label: str | None = None


class CaseReferenceApproval(BaseModel):
    selected_images: list[CaseReferenceImage] = Field(min_length=4, max_length=4)


def _candidate_source(url: str, fallback: str = "manual") -> str:
    lowered = url.lower()
    if "amazon." in lowered or "media-amazon.com" in lowered:
        return "amazon"
    if "apnx.com" in lowered or "corsair.com" in lowered or "lian-li.com" in lowered:
        return "manufacturer"
    return fallback


def _append_candidate(items: list[dict], seen: set[str], url: object, source: str, source_page: str | None = None, label: str | None = None) -> None:
    if not isinstance(url, str) or not url.startswith(("https://", "http://")) or url in seen:
        return
    seen.add(url)
    items.append({"url": url, "source": _candidate_source(url, source), "source_page": source_page, "label": label})


def _case_identity(case: Case) -> str:
    name = f"{case.brand or ''} {case.model or ''}".strip() if case.model else case.name
    return re.split(r"\s+(?:ARGB|RGB|Panoramic|Tempered|Glass|Mid[- ]Tower|PC Case)\b", name, maxsplit=1, flags=re.I)[0].strip()


def _exact_case_match(case: Case, title: str) -> bool:
    identity = _case_identity(case)
    required = re.findall(r"[a-z0-9]+", identity.lower())
    actual = re.findall(r"[a-z0-9]+", title.lower())
    if not required or not all(token in actual for token in required):
        return False
    # Preserve the chassis colour when the catalogued product specifies it.
    colours = {"black", "white", "silver", "pink", "red", "blue"}
    expected_colour = next((token for token in re.findall(r"[a-z0-9]+", case.name.lower()) if token in colours), None)
    actual_colours = colours.intersection(actual)
    return not (expected_colour and actual_colours and expected_colour not in actual_colours)


async def _matched_vendor_listings(case: Case, db: AsyncSession) -> list[Listing]:
    identity = _case_identity(case)
    distinctive = next((token for token in re.findall(r"[a-z0-9]+", identity.lower()) if any(c.isdigit() for c in token)), None)
    if not distinctive:
        return []
    rows = (await db.execute(select(Listing).where(Listing.title.ilike(f"%{distinctive}%"), Listing.image_urls.isnot(None)).limit(500))).scalars().all()
    return [row for row in rows if row.image_urls and _exact_case_match(case, row.title)]


async def _matched_case_offers(case: Case, db: AsyncSession) -> list[Case]:
    distinctive = next((token for token in re.findall(r"[a-z0-9]+", _case_identity(case).lower()) if any(c.isdigit() for c in token)), None)
    if not distinctive:
        return []
    rows = (await db.execute(select(Case).where(Case.name.ilike(f"%{distinctive}%"), Case.image_url.isnot(None)))).scalars().all()
    return [row for row in rows if _exact_case_match(case, row.name)]


@router.get("/{case_id}/3d-reference-candidates")
async def get_3d_reference_candidates(case_id: int, db: AsyncSession = Depends(get_db)):
    """Collate candidate photos without silently deciding which four are sent to Meshy."""
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = dict(case.sourcing_3d_evidence or {})
    stages = dict(evidence.get("stages") or {})
    product_stage = dict(stages.get("product_images") or {})
    vendor_candidates: list[dict] = []
    vendor_names: set[str] = set()
    seen: set[str] = set()
    for offer in await _matched_case_offers(case, db):
        vendor_candidates.append({"url": offer.image_url, "source": "retailer", "source_page": offer.source_url, "label": f"{offer.source_site} · {offer.name}"})
        seen.add(offer.image_url)
        vendor_names.add(offer.source_site)
    for listing in await _matched_vendor_listings(case, db):
        vendor = listing.source_name or "Vendor listing"
        main_image = next((url for url in listing.image_urls if isinstance(url, str) and url.startswith(("https://", "http://"))), None)
        if main_image:
            _append_candidate(vendor_candidates, seen, main_image, "retailer", listing.url, f"{vendor} · {listing.title}")
            vendor_names.add(vendor)

    approved = product_stage.get("approved_selection") or {}
    return {
        "case_id": case.id,
        "case_name": case.name,
        "sourcing_ready": (
            (stages.get("manufacturer_3d") or {}).get("status") in ("not_found", "complete")
            and (stages.get("third_party_3d") or {}).get("status") == "not_found"
        ),
        "candidates": vendor_candidates,
        "vendor_count": len(vendor_names),
        "vendor_names": sorted(vendor_names),
        "approved_selection": approved,
    }


@router.get("/{case_id}/3d-overclockers-gallery")
async def get_3d_overclockers_gallery(case_id: int, db: AsyncSession = Depends(get_db)):
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    offer = next((row for row in await _matched_case_offers(case, db) if "overclockers" in (row.source_site or "").lower()), None)
    listing = next((row for row in await _matched_vendor_listings(case, db) if "overclockers" in (row.source_name or "").lower()), None)
    fallback_urls = [offer.image_url] if offer and offer.image_url else []
    if listing:
        fallback_urls.extend(url for url in listing.image_urls or [] if isinstance(url, str))
    search_url = f"https://www.overclockers.co.uk/search?sSearch={quote_plus(_case_identity(case))}"
    try:
        async with managed_playwright(engine="patchright") as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto((offer.source_url if offer else None) or (listing.url if listing else search_url), wait_until="domcontentloaded", timeout=25000)
                if not offer and not listing:
                    links = await page.locator("a[href*='/product/']").all()
                    for link in links[:25]:
                        title = (await link.inner_text(timeout=1500)).strip()
                        if _exact_case_match(case, title):
                            await link.click(timeout=10000)
                            break
                if not _exact_case_match(case, await page.title()):
                    raise ValueError("Overclockers did not return the matching product page")
                image_urls: list[str] = []
                for _ in range(30):
                    urls = await page.locator(".swiper-slide img").evaluate_all("nodes => nodes.map(img => img.getAttribute('data-src') || img.getAttribute('src') || img.getAttribute('data-lazy-src')).filter(Boolean)")
                    image_urls.extend(urls)
                    next_button = page.locator(".swiper-button-next[aria-label='Next slide']").first
                    if not await next_button.count() or await next_button.get_attribute("aria-disabled") == "true":
                        break
                    await next_button.click(timeout=2000)
                from urllib.parse import urljoin
                results: list[dict] = []
                seen: set[str] = set()
                for raw in image_urls:
                    url = urljoin(page.url, raw)
                    if url not in seen and url.startswith("https://"):
                        seen.add(url)
                        results.append({"url": url, "source": "retailer", "source_page": page.url, "label": f"Overclockers · {_case_identity(case)}"})
                return {"results": results, "source_page": page.url}
            finally:
                await browser.close()
    except Exception:
        return {
            "results": [{"url": url, "source": "retailer", "source_page": offer.source_url if offer else listing.url if listing else None, "label": f"Overclockers · {_case_identity(case)}"} for url in dict.fromkeys(fallback_urls)],
            "source_page": offer.source_url if offer else listing.url if listing else None,
            "detail": "Overclockers blocked the live gallery; showing saved product photos",
        }


@router.get("/{case_id}/3d-reference-image-search")
async def search_3d_reference_images(
    case_id: int,
    query: str = Query(min_length=2, max_length=180),
    db: AsyncSession = Depends(get_db),
):
    """Search Google Images for owner-reviewed 3D reference candidates.

    Custom Search JSON API is Google's legacy image-search product. It is
    retained only while the configured project still has access.
    """
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY", "").strip()
    engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID", "").strip()
    if not api_key or not engine_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Images search is not configured. Add "
                "GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID to flipflop-api/.env."
            ),
        )

    params = {
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "searchType": "image",
        "safe": "active",
        "num": 10,
        "imgType": "photo",
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get("https://customsearch.googleapis.com/customsearch/v1", params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = "Google Images rejected the search request"
        try:
            detail = exc.response.json().get("error", {}).get("message") or detail
        except ValueError:
            pass
        if exc.response.status_code == 403 and "Custom Search JSON API" in detail:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Google Custom Search JSON API is not available to this project. "
                    "Google is retiring it: use Vertex AI Search for a site-restricted "
                    "search (up to 50 domains), or register interest with Google for "
                    "whole-web search. Upload approved reference images manually in the meantime."
                ),
            ) from exc
        raise HTTPException(status_code=502, detail=detail) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Google Images search failed: {exc}") from exc

    results = []
    for item in payload.get("items") or []:
        image_url = item.get("link")
        if not isinstance(image_url, str) or not image_url.startswith(("https://", "http://")):
            continue
        image_meta = item.get("image") or {}
        results.append({
            "url": image_url,
            "source": "google",
            "source_page": image_meta.get("contextLink"),
            "label": item.get("title") or f"Google Images · {case.name}",
            "thumbnail_url": image_meta.get("thumbnailLink") or image_url,
        })
    return {"query": query, "results": results}


@router.post("/{case_id}/3d-reference-candidates/upload")
async def upload_3d_reference_candidates(
    case_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Store owner-supplied photos and add them to the case's candidate set."""
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not files:
        raise HTTPException(status_code=422, detail="Choose at least one picture")
    if len(files) > 12:
        raise HTTPException(status_code=422, detail="Upload no more than 12 pictures at once")

    # Meshy must be able to fetch every approved reference from the public
    # internet, so local-only /uploads URLs are not sufficient here.
    CASE_REFERENCE_PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    uploaded: list[dict] = []
    created_paths: list[Path] = []
    try:
        for upload in files:
            extension = CASE_REFERENCE_UPLOAD_TYPES.get((upload.content_type or "").lower())
            if not extension:
                raise HTTPException(status_code=415, detail=f"{upload.filename or 'File'} must be JPG, PNG or WebP")
            content = await upload.read(CASE_REFERENCE_UPLOAD_LIMIT + 1)
            if not content:
                raise HTTPException(status_code=422, detail=f"{upload.filename or 'File'} is empty")
            if len(content) > CASE_REFERENCE_UPLOAD_LIMIT:
                raise HTTPException(status_code=413, detail=f"{upload.filename or 'File'} exceeds the 15 MB limit")
            filename = f"case-3d-ref-{case_id}-{uuid4().hex}{extension}"
            destination = CASE_REFERENCE_PUBLIC_ROOT / filename
            destination.write_bytes(content)
            created_paths.append(destination)
            if not await sync_to_public_media(destination):
                raise HTTPException(status_code=502, detail=f"Could not publish {upload.filename or 'picture'} for 3D generation")
            uploaded.append({
                "url": f"{CASE_REFERENCE_PUBLIC_URL}/{filename}",
                "source": "manual",
                "source_page": None,
                "label": f"Owner upload · {Path(upload.filename or 'picture').name[:120]}",
            })
    except Exception:
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise
    finally:
        for upload in files:
            await upload.close()

    evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
    stages = dict(evidence.get("stages") or {})
    product_stage = dict(stages.get("product_images") or {"attempts": []})
    existing = {item.get("url"): item for item in product_stage.get("candidate_images") or [] if isinstance(item, dict)}
    for item in uploaded:
        existing[item["url"]] = item
    product_stage.update({
        "candidate_images": list(existing.values()),
        "selection_required": True,
        "updated_at": datetime.utcnow().isoformat(),
    })
    stages["product_images"] = product_stage
    evidence["stages"] = stages
    case.sourcing_3d_evidence = evidence
    await db.commit()
    return {"uploaded": uploaded}


@router.post("/{case_id}/3d-reference-selection")
async def approve_3d_reference_selection(case_id: int, body: CaseReferenceApproval, db: AsyncSession = Depends(get_db)):
    """Persist the owner's four-photo approval as a gate separate from generation."""
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    urls = [str(item.url) for item in body.selected_images]
    if len(set(urls)) != 4:
        raise HTTPException(status_code=422, detail="Choose four different reference pictures")

    evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
    stages = dict(evidence.get("stages") or {})
    if (stages.get("manufacturer_3d") or {}).get("status") not in ("not_found", "complete"):
        raise HTTPException(status_code=409, detail="Finish the official/manufacturer 3D-model search before approving fallback photos")
    if (stages.get("third_party_3d") or {}).get("status") != "not_found":
        raise HTTPException(status_code=409, detail="Finish the licensed third-party 3D-model search before approving fallback photos")

    selected = [item.model_dump(mode="json") for item in body.selected_images]
    now = datetime.utcnow().isoformat()
    product_stage = dict(stages.get("product_images") or {"attempts": []})
    existing = {item.get("url"): item for item in product_stage.get("candidate_images") or [] if isinstance(item, dict)}
    for item in selected:
        existing[item["url"]] = item
    product_stage.update({
        "status": "complete",
        "candidate_images": list(existing.values()),
        "approved_selection": {
            "status": "approved",
            "images": selected,
            "approved_at": now,
            "texture_reference_url": urls[0],
            "requires_separate_model_approval": True,
        },
        "updated_at": now,
    })
    stages["product_images"] = product_stage
    evidence["stages"] = stages
    case.sourcing_3d_evidence = evidence
    case.status = "ready_for_approval"
    await db.commit()
    return _priority_payload(case, await _preferred_case_names(db))


@router.patch("/{case_id}/3d-sourcing")
async def update_3d_sourcing_evidence(
    case_id: int,
    body: SourcingEvidencePatch,
    db: AsyncSession = Depends(get_db),
):
    if body.stage not in SOURCING_STAGES:
        raise HTTPException(status_code=422, detail=f"Unknown sourcing stage '{body.stage}'")
    if body.stage == "product_images" and body.status == "complete":
        assessments = (body.attempt or {}).get("image_assessments") or []
        eligible = [
            item for item in assessments
            if isinstance(item, dict)
            and isinstance(item.get("url"), str)
            and all(item.get(field) is True for field in CASE_MESHY_PHOTO_REQUIREMENTS)
        ]
        if not eligible:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Product-image acquisition cannot be completed until at least one photo shows the same empty "
                    "chassis with its included RGB fans installed and illuminated, without text, dimensions, or an exploded view."
                ),
            )
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
    stages = dict(evidence.get("stages") or {})
    stage = dict(stages.get(body.stage) or {"attempts": []})
    attempts = list(stage.get("attempts") or [])
    if body.attempt is not None:
        attempts.append({**body.attempt, "recorded_at": datetime.utcnow().isoformat()})
    stage.update({"status": body.status, "attempts": attempts, "updated_at": datetime.utcnow().isoformat()})
    stages[body.stage] = stage
    evidence["stages"] = stages
    case.sourcing_3d_evidence = evidence
    case.status = "sourcing" if body.status not in ("complete", "blocked") else case.status
    await db.commit()
    return _priority_payload(case, await _preferred_case_names(db))


@router.get("/priority-for-3d")
async def get_cases_priority_for_3d(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    Get PC cases prioritized for 3D model creation.
    Sorted by Amazon bestseller rank (most popular first), then by source + price.
    Returns only cases without 3D models yet.
    """
    from sqlalchemy import case as sql_case

    frozen_exists = (await db.execute(select(func.count()).select_from(Case).where(Case.priority_3d_rank.isnot(None)))).scalar_one()
    priority_filter = (
        and_(Case.has_3d_model == False, Case.priority_3d_rank.isnot(None))
        if frozen_exists
        else Case.has_3d_model == False
    )
    result = await db.execute(
        select(Case)
        .where(priority_filter, ~Case.name.ilike("%raspberry%"))
        .order_by(
            Case.priority_3d_rank.asc().nullslast() if frozen_exists else Case.bestseller_rank.asc().nullslast(),
            sql_case((Case.source_site == "Amazon", 0), else_=1),  # Amazon prioritized
            Case.price.asc(),  # Cheaper cases first
        )
        .limit(limit)
    )
    cases = result.scalars().all()
    preferred_names = await _preferred_case_names(db)
    payloads = []
    for case in cases:
        payload = _priority_payload(case, preferred_names)
        vendors = {row.source_name for row in await _matched_vendor_listings(case, db) if row.source_name}
        vendors.update(row.source_site for row in await _matched_case_offers(case, db) if row.source_site)
        payload["vendor_count"] = len(vendors)
        payloads.append(payload)
    return payloads


@router.get("/with-3d-models")
async def get_cases_with_3d_models(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    Get cases that have 3D models ready.
    Use for website/builder display.
    """
    result = await db.execute(
        select(Case)
        .where(
            and_(
                Case.has_3d_model == True,
            )
        )
        .order_by(Case.bestseller_rank.asc().nullslast())
        .limit(limit)
    )
    cases = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "model": c.model,
            "price": c.price_new or c.price or 0,
            "source_site": c.source_site,
            "image_url": c.image_url,
            "bestseller_rank": c.bestseller_rank,
            "rating": c.rating,
            "review_count": c.review_count,
            "sales_velocity": c.sales_velocity,
            "keywords": c.keywords or [],
            "form_factors": c.form_factors or [],
            "model_3d_url": c.model_3d_url,
            "has_3d_model": True,
            "status": c.status,
            "sourcing_3d_evidence": c.sourcing_3d_evidence or {},
        }
        for c in cases
    ]


@router.get("/gallery")
async def get_gallery_cases(
    limit: int = 32,
    sort_by: str = "reviews",
    db: AsyncSession = Depends(get_db),
):
    """
    Get cases for the 3D review gallery.
    Sorted by: has_3d_model first, then by sort_by (reviews, rating, price, name).
    """
    from sqlalchemy import case as sql_case, desc

    # Build order clause: 3D models first, then by selected sort
    order_clauses = [
        sql_case((Case.has_3d_model == True, 0), else_=1),  # 3D models first
    ]

    if sort_by == "reviews":
        order_clauses.append(desc(Case.review_count))
    elif sort_by == "rating":
        order_clauses.append(desc(Case.rating))
    elif sort_by == "price":
        order_clauses.append(Case.price.asc())
    elif sort_by == "name":
        order_clauses.append(Case.name.asc())
    else:
        order_clauses.append(desc(Case.review_count))

    result = await db.execute(
        select(Case)
        .order_by(*order_clauses)
        .limit(limit)
    )
    cases = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "model": c.model,
            "price": c.price_new or c.price or 0,
            "source_site": c.source_site,
            "image_url": c.image_url,
            "rating": c.rating or 0,
            "review_count": c.review_count or 0,
            "form_factors": c.form_factors or [],
            "keywords": c.keywords or [],
            "has_3d_model": c.has_3d_model,
            "model_3d_url": c.model_3d_url,
            "status": "has-model" if c.has_3d_model else "reference-only",
        }
        for c in cases
    ]


@router.get("/stats")
async def get_cases_stats(db: AsyncSession = Depends(get_db)):
    """Get sourcing statistics."""
    from sqlalchemy import Integer

    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum((Case.has_3d_model == True).cast(Integer)).label("with_model"),
        ).select_from(Case)
    )
    row = result.first()
    return {
        "total_cases": row.total or 0,
        "with_3d_model": row.with_model or 0,
        "pending_3d_models": (row.total or 0) - (row.with_model or 0),
    }
