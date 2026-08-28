"""PC Case sourcing and 3D model management endpoints."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.case import Case
from app.models.catalogue import CaseCatalogue
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


def _priority_payload(case: Case) -> dict:
    return {
        "id": case.id,
        "name": case.name,
        "brand": case.brand,
        "model": case.model,
        "price": case.price_new or case.price or 0,
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
        "status": case.status,
        "sourcing_3d_evidence": case.sourcing_3d_evidence or {},
    }


@router.post("/priority-for-3d/freeze")
async def freeze_top_30_3d_campaign(db: AsyncSession = Depends(get_db)):
    """Freeze the current top 30 into three stable ten-case work batches."""
    from sqlalchemy import case as sql_case

    existing = (
        await db.execute(
            select(Case).where(Case.priority_3d_rank.isnot(None)).order_by(Case.priority_3d_rank)
        )
    ).scalars().all()
    if existing:
        return {"frozen": False, "reason": "campaign_already_frozen", "cases": [_priority_payload(case) for case in existing]}

    ranked = (
        await db.execute(
            select(Case)
            .where(Case.has_3d_model == False)  # noqa: E712
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
    return {"frozen": True, "cases": [_priority_payload(case) for case in ranked]}


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


@router.get("/{case_id}/3d-reference-candidates")
async def get_3d_reference_candidates(case_id: int, db: AsyncSession = Depends(get_db)):
    """Collate candidate photos without silently deciding which four are sent to Meshy."""
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = dict(case.sourcing_3d_evidence or {})
    stages = dict(evidence.get("stages") or {})
    product_stage = dict(stages.get("product_images") or {})
    candidates: list[dict] = []
    seen: set[str] = set()
    _append_candidate(candidates, seen, case.image_url, _candidate_source(case.image_url or ""), case.source_url, "Catalogue image")

    for item in product_stage.get("candidate_images") or []:
        if isinstance(item, dict):
            _append_candidate(candidates, seen, item.get("url"), item.get("source") or "manual", item.get("source_page"), item.get("label"))
    for url in product_stage.get("urls") or []:
        _append_candidate(candidates, seen, url, "manual", case.source_url)
    for attempt in product_stage.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        source = attempt.get("source") or attempt.get("provider") or "manual"
        source_page = attempt.get("source_page") or attempt.get("source_url")
        for key in ("image_urls", "urls", "source_image_urls"):
            for url in attempt.get(key) or []:
                _append_candidate(candidates, seen, url, str(source).lower(), source_page)
        for assessment in attempt.get("image_assessments") or []:
            if isinstance(assessment, dict):
                _append_candidate(candidates, seen, assessment.get("url"), str(source).lower(), source_page)

    # Amazon galleries captured by FlipflopXtension are stored on the case
    # catalogue. Match conservatively by brand plus model/name tokens.
    catalogue_rows = (await db.execute(select(CaseCatalogue).where(CaseCatalogue.brand.ilike(case.brand or "%")))).scalars().all()
    model_tokens = [token.lower() for token in (case.model or "").replace("-", " ").split() if len(token) > 1]
    for row in catalogue_rows:
        haystack = row.name.lower()
        if model_tokens and not all(token in haystack for token in model_tokens):
            continue
        for url in row.images or []:
            _append_candidate(candidates, seen, url, "amazon", case.source_url, f"Stored Amazon gallery · {row.name}")

    approved = product_stage.get("approved_selection") or {}
    return {
        "case_id": case.id,
        "case_name": case.name,
        "sourcing_ready": (
            (stages.get("manufacturer_3d") or {}).get("status") in ("not_found", "complete")
            and (stages.get("third_party_3d") or {}).get("status") == "not_found"
        ),
        "candidates": candidates,
        "approved_selection": approved,
    }


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
    return _priority_payload(case)


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
    return _priority_payload(case)


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
        .where(priority_filter)
        .order_by(
            Case.priority_3d_rank.asc().nullslast() if frozen_exists else Case.bestseller_rank.asc().nullslast(),
            sql_case((Case.source_site == "Amazon", 0), else_=1),  # Amazon prioritized
            Case.price.asc(),  # Cheaper cases first
        )
        .limit(limit)
    )
    cases = result.scalars().all()

    return [_priority_payload(case) for case in cases]


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
