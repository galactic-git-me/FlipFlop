from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, String
from sqlalchemy.sql.expression import cast as sa_cast
from app.database import get_db
from app.models.listing import Listing, ListingStatus, Classification
from app.schemas.listing import ListingAlternative, ListingOut, ListingFilter

router = APIRouter(prefix="/listings", tags=["listings"])

_CLAUDE_VERDICTS = {"GEM", "GOOD", "MAYBE", "REJECT"}


def _build_gem_explainer(listing: Listing) -> str:
    # Prefer Claude's reasoning when available
    if listing.claude_reasoning:
        verdict_label = f"[{listing.claude_verdict}] " if listing.claude_verdict else ""
        risk_text = f" Risk: {listing.claude_main_risk}" if listing.claude_main_risk else ""
        return f"{verdict_label}{listing.claude_reasoning}{risk_text}"
    signals = listing.gem_signals or []
    top = ", ".join(signals[:3]) if signals else "baseline value opportunity"
    risks = []
    if listing.seller_type in {"private", None}:
        risks.append("private seller risk")
    if listing.listing_type == "auction":
        risks.append("auction final price can drift")
    if listing.resale_comp_count is not None and listing.resale_comp_count < 3:
        risks.append("limited sold comps")
    risk_text = f" Risks: {', '.join(risks)}." if risks else ""
    return f"Flagged for {top}.{risk_text}"


@router.get("/", response_model=list[ListingOut])
@router.get("", response_model=list[ListingOut], include_in_schema=False)
async def get_listings(
    classification: Classification | None = Query(None),
    claude_verdict: str | None = Query(None),
    status: ListingStatus | None = Query(ListingStatus.active),
    source_name: str | None = Query(None),
    min_profit: float | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    search: str | None = Query(None),
    first_seen_after: datetime | None = Query(None),
    claude_judged_after: datetime | None = Query(None),
    claude_judged_only: bool = Query(False),
    gem_only: bool = Query(False),
    whole_pc_only: bool = Query(False),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    sort_by: str = Query("gem_score"),
    sort_desc: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    # Build filter conditions as a list so they can be reused in the dedup subquery
    conditions = []
    if status:
        conditions.append(Listing.status == status)

    # Always exclude defective/incomplete items — "For parts or not working" should never appear
    defect_patterns = [
        "For Parts", "For Spares", "For Repair", "Not Working", "Parts Only",
        "Spares Only", "Broken", "Faulty", "Dead", "Damaged"
    ]
    for pattern in defect_patterns:
        conditions.append(~Listing.title.ilike(f"%{pattern}%"))
    if classification:
        conditions.append(Listing.classification == classification)
    if claude_verdict and claude_verdict.upper() in _CLAUDE_VERDICTS:
        conditions.append(Listing.claude_verdict == claude_verdict.upper())
    if source_name:
        conditions.append(Listing.source_name == source_name)
    if min_profit is not None:
        # Use Claude expected profit when available, fall back to estimated
        conditions.append(
            (Listing.claude_expected_profit >= min_profit) |
            ((Listing.claude_expected_profit == None) & (Listing.estimated_profit >= min_profit))
        )
    if min_price is not None:
        conditions.append(Listing.price >= min_price)
    if max_price is not None:
        conditions.append(Listing.price <= max_price)
    if search:
        conditions.append(Listing.title.ilike(f"%{search}%"))
    if first_seen_after is not None:
        # DB stores naive datetimes — strip tzinfo to avoid comparison error
        fsa = first_seen_after.replace(tzinfo=None)
        conditions.append(Listing.first_seen_at >= fsa)
    if claude_judged_after is not None:
        cja = claude_judged_after.replace(tzinfo=None)
        conditions.append(Listing.claude_judged_at >= cja)
    if gem_only:
        # Include rule-based gems AND LLM-confirmed gems
        conditions.append(
            Listing.classification.in_([Classification.amazing_gem, Classification.gem])
        )
    if claude_judged_only:
        conditions.append(Listing.claude_judged_at != None)
    if whole_pc_only:
        # Exclude listings whose titles are unambiguously standalone components
        # (not whole PC systems). Uses conservative patterns that are very unlikely
        # to appear in whole-PC system listings.
        _COMPONENT_PATTERNS = [
            # Memory modules — these substrings identify RAM sticks, not PCs with RAM
            "%Laptop Memory%",
            "%Desktop Memory%",
            "%Server Memory%",
            "% DIMM%",            # e.g. "16GB DIMM" — RAM module
            "%SO-DIMM%",
            "%SODIMM%",
            "%DDR4 (%",           # "32GB DDR4 (2x16@2400T MHz)" — RAM kit spec in parens
            "%DDR5 (%",
            "%DDR3 (%",
            "%for server%",       # "DDR4 for server/workstation" — component listing
            "%for workstation%",
            # Explicit GPU/graphics card listings (not PCs containing a GPU)
            "%Graphics Card%",
            "%Video Card%",
            "%Graphic Card%",
            # NVMe/M.2 drives explicitly sold as drives (Job Lot = bulk component sale)
            "%Job Lot%NVMe%",
            "%NVMe%Job Lot%",
            "%Job Lot%SSD%",
            "%SSD%Job Lot%",
            "%Job Lot%DDR%",
            "%DDR%Job Lot%",
            "%Job Lot%M.2%",
            "%M.2%Job Lot%",
            # M.2 SSD explicitly listed as a drive product (has capacity + M.2 + NVMe/SSD)
            "%M.2%NVMe%SSD%",    # "256GB M.2 NVMe SSD" — drive listing
            "%NVMe%SSD%M.2%",
            # CPU-only listings
            "%Processor%OEM%",
            "%CPU Tray%",
            "%- Brand New%",      # "Ryzen 7 7800X3D - Brand New" — boxed component, not a PC
            "% Brand New Sealed%",
            "% Brand New Boxed%",
            # PSU / power supply standalone listings
            "%Power Supply Unit%",
            "%Modular PSU%",
            "% PSU%",             # "275W PSU H275P-00", "Modular PSU"
            "%W PSU%",            # "750W PSU", "550W PSU"
            "%Power Supply%",     # "Dell Power supply N750P-00" (broader than "Power Supply Unit")
            # CPU cooling / heatsink standalone
            "%CPU Fan%",
            "%CPU Cooling Fan%",
            "%CPU Cooler%",
            "% Heatsink%",
            "%Heat Sink%",
            # Motherboard standalone (explicit keyword or common mobo-only bundle patterns)
            "%Motherboard%",
            "%Mainboard%",
            "%RGB Bundle%",        # "Corsair RGB Bundle" — component RGB bundle, not a PC
            "%AM4 +%",            # "X570 AM4 + Ryzen 9..." — mobo+CPU bundle, not a whole PC
            "%AM4,%",             # "X570 AM4, Ryzen 9..." — same bundle with comma separator
            "%AM5 +%",
            "%AM5,%",
            "%LGA1700 +%",
            "%LGA1700,%",
            "%LGA1200 +%",
            "%LGA1200,%",
            "%LGA1151 +%",
            "%LGA1151,%",
            "%AM4+%",
            "%AM5+%",
            # For parts / not working — incomplete systems not worth flipping
            "%For Parts%",
            "%For Spares%",
            "%Parts Only%",
            "%Spares Only%",
            "%For Repair%",
            "% - Spares%",
            # Missing key components (no CPU, no RAM etc in title signals incomplete)
            "%No CPU%",
            "%No GPU%",
            "%No RAM%",
            "%No SSD%",
            "%No HDD%",
            "%No Hard Drive%",
            "%No Storage%",
            "%No Drives%",
            "%No Drive%",
            # Barebones chassis (no CPU/RAM/storage)
            "%Barebones%",
            "%Bare Bones%",
            "%Barebone%",
            # Peripherals and accessories
            "% Speakers%",        # "Stereo Speakers", "USB Speakers" — not a PC
            "%Speaker System%",
            "%Wireless Antenna%",
            "%Network Antenna%",
            "%WiFi Antenna%",
            "% Antenna%",         # standalone antenna part
            "%Stand for%",        # "Stand for Dell AIO" — not the PC itself
            "%Monitor Stand%",
            "%AIO Stand%",
            # Drive caddies / trays / enclosures
            "%Hard Drive Caddy%",
            "%Hard Drive Tray%",
            "%HDD Caddy%",
            "%SSD Caddy%",
            "%Drive Caddy%",
            "%Drive Tray%",
            # Standalone storage drives (not job lots — those covered above)
            "%External Hard Drive%",
            "%External SSD%",
            "%Portable SSD%",
            "%Portable Hard%",
            "%Internal Solid State Drive%",   # "NVMe M.2 Internal Solid State Drive" — SSD listing
            "%Internal Solid State%",
            "%Solid State Drive%",            # catches titles that spell it out instead of SSD
            "%Internal Hard Drive%",
            # Standalone networking cards
            "%WiFi Card%",
            "%Wireless Card%",
            "%Network Card%",
            "%WiFi Adapter%",
            "%WiFi Module%",
            # Case fans (not whole-PC cooling)
            "%Case Fan%",
            "%Case Cooling Fan%",
            "% mm Fan%",          # "140mm Fan", "120mm Fan" — clearly a fan, not a PC
            # PC case (chassis only, not a complete system)
            "%PC Case%",
            "%ATX Case%",
            "%mATX Case%",
            "%ITX Case%",
            "%Tower Case%",
            # Laptop / notebook / handheld signals
            "% Notebook%",        # "HP Pavilion TS 11 Notebook PC"
            "%Laptop PC%",
            "%Mobile Workstation%",   # HP ZBook, Dell Precision mobile — laptops
            "%ZBook%",                # All HP ZBook models are laptops/mobile workstations
            "%Steam Deck%",           # Valve handheld gaming console
            "%Handheld Console%",
            "%Portable Console%",
            # Thin clients are not flippable desktop PCs
            "%Thin Client%",
            # Upgrade / starter kits — not a complete PC
            "%Upgrade Kit%",
            "%Starter Kit%",
            "% upgrade /starter%",
            # Laptop (screen size in title is a reliable laptop signal)
            "% 15.6%inch%",
            "% 14%inch%",
            "% 13.3%inch%",
            "% 15.6\"%",
            "% 14\"%",
            "% 13.3\"%",
        ]
        from sqlalchemy import or_, not_
        is_component = or_(*[Listing.title.ilike(p) for p in _COMPONENT_PATTERNS])
        conditions.append(not_(is_component))

    # Spec-based deduplication: for listings sharing the same hardware spec fingerprint
    # (same CPU/GPU/RAM/storage), only surface the cheapest one.
    # Listings without a spec_fingerprint are treated as their own unique group (by id).
    fp_expr = func.coalesce(Listing.spec_fingerprint, sa_cast(Listing.id, String))
    rn_col = func.row_number().over(
        partition_by=fp_expr,
        order_by=[Listing.price.asc(), Listing.id.asc()],
    ).label("rn")
    ranked_sq = select(Listing.id.label("id"), rn_col).where(*conditions).subquery("ranked")
    cheapest_ids = select(ranked_sq.c.id).where(ranked_sq.c.rn == 1)

    sort_col = getattr(Listing, sort_by, Listing.gem_score)
    q = (
        select(Listing)
        .where(*conditions)
        .where(Listing.id.in_(cheapest_ids))
        .order_by(sort_col.desc() if sort_desc else sort_col.asc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(q)
    rows = result.scalars().all()

    # Fetch cross-vendor alternatives: all active listings that share a spec_fingerprint
    # with one of the returned rows (but weren't returned themselves — they're pricier).
    returned_ids = {r.id for r in rows}
    spec_fps = [r.spec_fingerprint for r in rows if r.spec_fingerprint]
    alts_by_fp: dict[str, list[ListingAlternative]] = defaultdict(list)
    if spec_fps:
        alt_res = await db.execute(
            select(
                Listing.id,
                Listing.spec_fingerprint,
                Listing.source_name,
                Listing.price,
                Listing.url,
            ).where(
                Listing.spec_fingerprint.in_(spec_fps),
                Listing.status == ListingStatus.active,
                Listing.id.notin_(returned_ids),
            ).order_by(Listing.price.asc())
        )
        for row in alt_res.all():
            alts_by_fp[row.spec_fingerprint].append(
                ListingAlternative(
                    id=row.id,
                    source_name=row.source_name,
                    price=row.price,
                    url=row.url,
                )
            )

    out = []
    for r in rows:
        item = ListingOut.model_validate(r).model_dump()
        item["gem_explainer"] = _build_gem_explainer(r)
        item["alternatives"] = [
            a.model_dump() for a in alts_by_fp.get(r.spec_fingerprint or "", [])
        ]
        out.append(item)
    return out


@router.get("/stats")
async def get_listing_stats(
    first_seen_after: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Single-query stats — avoids the N round-trip latency on large SQLite DBs."""
    from sqlalchemy import case

    # Profit expression — same field used for avg, min, and max so they're consistent
    _gem_profit = case(
        (
            (Listing.claude_verdict.in_(["GEM", "GOOD"])) &
            (Listing.claude_expected_profit > 0),
            Listing.claude_expected_profit,
        ),
        (
            (Listing.classification.in_([Classification.amazing_gem, Classification.gem])) &
            (Listing.claude_judged_at == None) &
            (Listing.estimated_profit > 0),
            Listing.estimated_profit,
        ),
        else_=None,
    )

    # One pass over the table: count + conditional aggregates
    row = await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((Listing.claude_verdict.in_(["GEM", "GOOD"]), 1), else_=0)).label("claude_gems"),
            func.sum(case((Listing.claude_judged_at != None, 1), else_=0)).label("claude_judged"),
            func.sum(case(
                (
                    (Listing.classification.in_([Classification.amazing_gem, Classification.gem])) &
                    (Listing.claude_judged_at == None),
                    1,
                ),
                else_=0,
            )).label("rule_gems"),
            func.sum(case(
                (Listing.claude_verdict == "GEM", 1),
                (
                    (Listing.classification == Classification.amazing_gem) &
                    (Listing.claude_judged_at == None),
                    1,
                ),
                else_=0,
            )).label("super_gems"),
            func.avg(_gem_profit).label("avg_profit"),
            func.min(_gem_profit).label("min_profit"),
            func.max(_gem_profit).label("max_profit"),
        ).select_from(Listing)
        .where(
            Listing.status == ListingStatus.active,
            *(
                [Listing.first_seen_at >= first_seen_after.replace(tzinfo=None)] if first_seen_after else []
            ),
        )
    )
    r = row.one()

    # Per-source counts from current listings (not cumulative listings_found_total)
    src_rows = await db.execute(
        select(Listing.source_name, func.count().label("cnt"))
        .select_from(Listing)
        .where(
            Listing.status == ListingStatus.active,
            *(
                [Listing.first_seen_at >= first_seen_after.replace(tzinfo=None)] if first_seen_after else []
            ),
        )
        .group_by(Listing.source_name)
    )
    by_source_listings: dict[str, int] = {row.source_name: int(row.cnt) for row in src_rows}

    gem_src_rows = await db.execute(
        select(Listing.source_name, func.count().label("cnt"))
        .select_from(Listing)
        .where(
            Listing.status == ListingStatus.active,
            *(
                [Listing.first_seen_at >= first_seen_after.replace(tzinfo=None)] if first_seen_after else []
            ),
            (
                Listing.claude_verdict.in_(["GEM", "GOOD"]) |
                (
                    Listing.classification.in_([Classification.amazing_gem, Classification.gem]) &
                    (Listing.claude_judged_at == None)
                )
            ),
        )
        .group_by(Listing.source_name)
    )
    by_source_gems: dict[str, int] = {row.source_name: int(row.cnt) for row in gem_src_rows}

    from app.services.claude_eval_queue import queue_size
    unjudged = int(r.total or 0) - int(r.claude_judged or 0)
    return {
        "total_listings":        int(r.total or 0),
        "gems_count":            int((r.claude_gems or 0) + (r.rule_gems or 0)),
        "super_gems_count":      int(r.super_gems or 0),
        "avg_profit":            round(float(r.avg_profit or 0), 2),
        "min_profit":            round(float(r.min_profit or 0), 2),
        "max_profit":            round(float(r.max_profit or 0), 2),
        "claude_judged_count":   int(r.claude_judged or 0),
        "claude_gems_count":     int(r.claude_gems or 0),
        "rule_based_gems_count": int(r.rule_gems or 0),
        "claude_eval_queue":     queue_size(),
        "claude_unjudged_count": max(0, unjudged),
        "by_source_listings":    by_source_listings,
        "by_source_gems":        by_source_gems,
    }


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    item = ListingOut.model_validate(listing).model_dump()
    item["gem_explainer"] = _build_gem_explainer(listing)
    return item


@router.patch("/{listing_id}/status")
async def update_listing_status(
    listing_id: int,
    status: ListingStatus,
    db: AsyncSession = Depends(get_db),
):
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    listing.status = status
    return {"ok": True, "status": status}


@router.post("/{listing_id}/re-evaluate")
async def re_evaluate_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Force a Claude re-evaluation of this listing (clears previous verdict first)."""
    from app.services.claude_eval_queue import enqueue_for_claude
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    listing.claude_judged_at = None  # allow re-evaluation
    await db.commit()
    enqueue_for_claude(listing_id)
    return {"ok": True, "queued": True, "listing_id": listing_id}


@router.post("/force-eval-source")
async def force_eval_source(
    source_name: str = Query(...),
    limit: int = Query(2000, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Force Claude evaluation of ALL active listings from a given source,
    bypassing the should_queue_for_claude gem-only gate. Clears previous verdicts."""
    from app.services.claude_eval_queue import enqueue_for_claude, queue_size
    result = await db.execute(
        select(Listing)
        .where(
            Listing.source_name == source_name,
            Listing.status == ListingStatus.active,
        )
        .order_by(Listing.gem_score.desc().nulls_last())
        .limit(limit)
    )
    listings = result.scalars().all()
    for listing in listings:
        listing.claude_judged_at = None
    await db.commit()
    queued = sum(1 for l in listings if enqueue_for_claude(l.id))
    return {
        "ok": True,
        "source": source_name,
        "queued": queued,
        "total": len(listings),
        "queue_size": queue_size(),
    }


@router.post("/queue-for-claude")
async def queue_unjudged_for_claude(
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """
    Queue up to `limit` active listings that haven't been Claude-evaluated yet.
    Use this to backfill Claude verdicts for your existing catalogue.
    """
    from app.services.claude_eval_queue import enqueue_for_claude, should_queue_for_claude, queue_size
    result = await db.execute(
        select(Listing)
        .where(
            Listing.claude_judged_at == None,
            Listing.status == ListingStatus.active,
        )
        .order_by(Listing.gem_score.desc())
        .limit(limit)
    )
    listings = result.scalars().all()
    queued = 0
    for listing in listings:
        if should_queue_for_claude(listing):
            if enqueue_for_claude(listing.id):
                queued += 1
    return {
        "ok": True,
        "queued": queued,
        "total_candidates": len(listings),
        "queue_size": queue_size(),
    }


@router.post("/analyze")
async def analyze_listings(
    data: dict,
):
    """
    Analyze marketplace listings with LLM to find top 5 deals.
    Uses OpenRouter (Google Gemma 4 31B free model) like gem evaluator.
    """
    import httpx
    import asyncio
    from app.config import get_settings

    listings = data.get("listings", [])
    if not listings:
        raise HTTPException(status_code=400, detail="No listings provided")

    settings = get_settings()
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")

    # Format listings for LLM
    listings_text = "\n".join(
        f"{i+1}. {l['title']} - £{l.get('price', 'N/A')} ({l.get('source', 'Unknown')}, {l.get('classification', 'unknown')})"
        for i, l in enumerate(listings[:30])  # Limit to 30 for context
    )

    prompt = f"""Analyze these marketplace listings and identify the TOP 5 BEST DEALS.

LISTINGS:
{listings_text}

For each top deal, explain:
1. Title and price
2. Why it's a good deal (profit margin, rarity, demand)
3. Estimated resale value
4. Risk factors

Format your response as a clear ranking with reasoning."""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "PC Flipper Listing Analyzer",
                },
                json={
                    "model": settings.openrouter_primary_model or "google/gemma-4-31b-it:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
            )

        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"OpenRouter API error: {resp.text}")

        result = resp.json()
        analysis_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not analysis_text:
            raise HTTPException(status_code=500, detail="No analysis returned from LLM")

        return {
            "analysis": analysis_text,
            "listings_analyzed": len(listings),
        }
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"API request failed: {str(e)}")
