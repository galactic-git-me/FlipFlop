from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import and_, select, update

from app.database import AsyncSessionLocal
from app.models.flip import Flip, FlipStage
from app.models.playbook import Playbook, PlaybookProposal
from app.models.source_search_term import SourceSearchTerm
from app.services.alerts import emit_alert
from app.services.demand_service import compute_demand
from app.services.external_demand import latest_external_signal_snapshot

log = structlog.get_logger(__name__)


def _latest_query_signal_map(external: dict) -> dict[str, dict]:
    """Return latest google_trends signal row by query (lowercased)."""
    out: dict[str, dict] = {}
    for item in (external.get("items", {}) or {}).get("google_trends", []) or []:
        q = str(item.get("query") or "").strip().lower()
        if not q:
            continue
        ts = str(item.get("signal_time") or "")
        prev = out.get(q)
        if not prev or ts > str(prev.get("signal_time") or ""):
            out[q] = item
    return out


def _score_for(signal_map: dict[str, dict], query: str) -> float:
    try:
        return float((signal_map.get(query.lower(), {}) or {}).get("score") or 0.0)
    except Exception:
        return 0.0


async def _pending_update_exists(db, playbook_id: int, marker: str) -> bool:
    result = await db.execute(
        select(PlaybookProposal).where(
            and_(
                PlaybookProposal.playbook_id == playbook_id,
                PlaybookProposal.action == "UPDATE",
                PlaybookProposal.status == "pending",
            )
        )
    )
    rows = list(result.scalars().all())
    for p in rows:
        ds = dict(p.demand_signals or {})
        if str(ds.get("source") or "") == marker:
            return True
    return False


async def _create_demand_rule_update(
    db,
    pb: Playbook,
    *,
    reason: str,
    marker: str,
    demand_signals: dict,
    keyword_add: list[str] | None = None,
    target_profit_multiplier: float | None = None,
) -> bool:
    if await _pending_update_exists(db, pb.id, marker):
        return False

    proposed_data: dict = {}
    if keyword_add:
        old_strategy = dict(pb.search_strategy or {})
        old_keywords = list(old_strategy.get("keywords", []) or [])
        merged = []
        seen = set()
        for kw in old_keywords + keyword_add:
            k = str(kw).strip()
            if not k:
                continue
            lk = k.lower()
            if lk in seen:
                continue
            seen.add(lk)
            merged.append(k)
        old_strategy["keywords"] = merged
        proposed_data["search_strategy"] = old_strategy

    if target_profit_multiplier is not None and target_profit_multiplier > 0:
        old_profit = dict(pb.profit_strategy or {})
        current_target = float(old_profit.get("target_profit_gbp") or 0.0)
        if current_target > 0:
            old_profit["target_profit_gbp"] = round(max(20.0, current_target * target_profit_multiplier), 0)
            proposed_data["profit_strategy"] = old_profit

    if not proposed_data:
        return False

    db.add(
        PlaybookProposal(
            action="UPDATE",
            playbook_id=pb.id,
            proposed_data=proposed_data,
            reason=reason,
            demand_signals=demand_signals,
            status="pending",
            proposed_at=datetime.utcnow(),
        )
    )
    return True


# ─── Score computation helpers ─────────────────────────────────────────────────

def _compute_market_size_score(listing_count: int, gem_count: int) -> float:
    """0-10 score: more active listings + gems = larger addressable market."""
    base = min(10.0, listing_count / 20.0)
    gem_boost = min(2.0, gem_count / 5.0)
    return round(min(10.0, base + gem_boost), 1)


def _compute_liquidity_score(avg_days_to_sell: float | None) -> float:
    """0-10 score: faster sales = higher liquidity."""
    if avg_days_to_sell is None:
        return 5.0
    if avg_days_to_sell <= 3:
        return 10.0
    if avg_days_to_sell <= 7:
        return 9.0
    if avg_days_to_sell <= 14:
        return 7.5
    if avg_days_to_sell <= 30:
        return 5.5
    if avg_days_to_sell <= 60:
        return 3.0
    return 1.0


def _compute_resellability_score(sold_count: int, listing_count: int, gem_count: int) -> float:
    """0-10: sell-through rate proxy."""
    if listing_count == 0:
        return 5.0
    sell_through = min(1.0, sold_count / max(1, listing_count))
    base = sell_through * 8.0
    gem_boost = min(2.0, gem_count / 3.0)
    return round(min(10.0, base + gem_boost), 1)


def _compute_risk_score(avg_days_to_sell: float | None, margin_pct: float | None, listing_count: int) -> float:
    """0-10: higher = more risky."""
    risk = 3.0
    if avg_days_to_sell and avg_days_to_sell > 30:
        risk += 2.0
    if avg_days_to_sell and avg_days_to_sell > 60:
        risk += 1.5
    if margin_pct and margin_pct < 20:
        risk += 2.0
    if listing_count < 5:
        risk += 1.0
    return round(min(10.0, risk), 1)


def _compute_composite_rank(
    profit_opportunity_score: float,
    market_size_score: float,
    liquidity_score: float,
    resellability_score: float,
    risk_score: float,
    expected_roi_pct: float,
) -> float:
    """Composite rank normalised to 0-100."""
    roi_factor = min(3.0, max(0.1, expected_roi_pct / 40.0))
    demand_factor = market_size_score / 10.0
    liquidity_factor = liquidity_score / 10.0
    resellability_factor = resellability_score / 10.0
    profit_factor = max(0.1, profit_opportunity_score / 5.0)
    risk_factor = max(0.1, (10.0 - risk_score) / 10.0)
    raw = roi_factor * demand_factor * liquidity_factor * resellability_factor * profit_factor * risk_factor
    return round(min(100.0, raw * 100.0), 2)


_USE_CASE_CAT_MAP: dict[str, list[str]] = {
    "gaming": ["Gaming PCs", "Budget Builders"],
    "budget": ["Budget Builders", "Office Clearance"],
    "workstation": ["Workstations"],
    "office": ["Office Clearance"],
    "ai_workstation": ["Workstations"],
    "htpc": ["HTPC / SFF"],
}


async def _refresh_playbook_scores(
    playbook: "Playbook",
    sold_flips: list,
    demand_categories: list,
) -> None:
    """Update all scores on a single playbook in-place (no DB flush — caller does that)."""
    use_case = str(playbook.target_use_case or "").lower()

    # Profit range from profit_model (seeded or previously computed)
    pm = dict(playbook.profit_model or {})
    expected_profit = float(pm.get("expected_profit") or 0)
    pricing = dict(playbook.pricing_model or {})
    expected_build = float(pricing.get("expected_build_cost") or 0)

    expected_roi_pct = 0.0
    if expected_build > 0 and expected_profit > 0:
        expected_roi_pct = round((expected_profit / expected_build) * 100, 1)

    # Market size from demand categories matching use_case
    relevant_cats = _USE_CASE_CAT_MAP.get(use_case, [])
    cat_listings = sum(c.get("count", 0) for c in demand_categories if c.get("name") in relevant_cats)
    cat_gems = sum(c.get("gem_count", 0) for c in demand_categories if c.get("name") in relevant_cats)
    playbook.market_size_score = _compute_market_size_score(cat_listings, cat_gems)

    # Liquidity from actual sold history or playbook avg_days_to_sell
    avg_days = float(playbook.avg_days_to_sell or 14)
    playbook.liquidity_score = _compute_liquidity_score(avg_days)

    # Resellability
    matching_sold = len([f for f in sold_flips if f.actual_profit is not None])
    playbook.resellability_score = _compute_resellability_score(matching_sold, max(1, cat_listings), cat_gems)

    # Risk
    margin_pct = expected_roi_pct if expected_roi_pct > 0 else None
    playbook.risk_score = _compute_risk_score(avg_days, margin_pct, cat_listings)

    # Growth direction from demand categories
    trend_votes = [c.get("trend", "") for c in demand_categories if c.get("name") in relevant_cats]
    growing = sum(1 for t in trend_votes if t == "Growing")
    shrinking = sum(1 for t in trend_votes if t == "Shrinking")
    if growing > shrinking:
        playbook.market_growth_direction = "Growing"
    elif shrinking > growing:
        playbook.market_growth_direction = "Shrinking"
    else:
        playbook.market_growth_direction = "Stable"

    # Composite rank
    playbook.composite_rank_score = _compute_composite_rank(
        playbook.profit_opportunity_score,
        playbook.market_size_score,
        playbook.liquidity_score,
        playbook.resellability_score,
        playbook.risk_score,
        expected_roi_pct,
    )

    playbook.last_reviewed = datetime.utcnow()


async def run_playbook_evolution() -> dict:
    """
    Nightly proposal generator.

    Heuristic v1:
    - Look at sold flips in last 30 days.
    - If avg actual profit is materially above active playbook target,
      propose a target increase.
    - If avg actual profit is materially below target, propose conservative reduction.

    Changes are proposals only; never auto-applied.
    """
    cutoff = datetime.utcnow() - timedelta(days=30)

    async with AsyncSessionLocal() as db:
        flips_result = await db.execute(
            select(Flip).where(
                and_(
                    Flip.stage == FlipStage.sold,
                    Flip.sold_at.is_not(None),
                    Flip.sold_at >= cutoff,
                    Flip.actual_profit.is_not(None),
                )
            )
        )
        sold_flips = list(flips_result.scalars().all())

        playbooks_result = await db.execute(select(Playbook).where(Playbook.status == "active"))
        playbooks = list(playbooks_result.scalars().all())

        demand_categories = await compute_demand(db)
        external = await latest_external_signal_snapshot(limit_per_source=50)
        proposals_created = 0

        # ── Phase 2-9: Score all active playbooks ─────────────────────────────
        playbooks_scored = 0
        for pb in playbooks:
            await _refresh_playbook_scores(pb, sold_flips, demand_categories)
            playbooks_scored += 1
        await db.flush()

        # Explicit demand rules from Google Trends buyer-intent queries.
        # These rules propose search-strategy updates; they do not auto-apply.
        gt = _latest_query_signal_map(external)
        score_ai = _score_for(gt, "ai pc")
        score_gaming = _score_for(gt, "gaming pc")
        score_budget = _score_for(gt, "budget gaming pc")
        score_workstation = _score_for(gt, "workstation pc")

        async def _apply_rule_to_use_case(
            use_case: str,
            *,
            trigger_score: float,
            threshold: float,
            marker: str,
            reason: str,
            keyword_add: list[str],
            target_profit_multiplier: float | None = None,
        ) -> int:
            if trigger_score < threshold:
                return 0
            created = 0
            for pb in playbooks:
                if str(pb.target_use_case or "").lower() != use_case:
                    continue
                ok = await _create_demand_rule_update(
                    db,
                    pb,
                    reason=reason,
                    marker=marker,
                    demand_signals={
                        "source": marker,
                        "query_score": round(trigger_score, 2),
                        "threshold": threshold,
                        "external_summary": external.get("summary", {}),
                    },
                    keyword_add=keyword_add,
                    target_profit_multiplier=target_profit_multiplier,
                )
                if ok:
                    created += 1
            return created

        proposals_created += await _apply_rule_to_use_case(
            "ai_workstation",
            trigger_score=score_ai,
            threshold=5.0,
            marker="demand_rules_v1_ai_pc",
            reason="Google Trends shows elevated 'ai pc' demand; expand AI workstation sourcing terms and nudge target profit.",
            keyword_add=["ai pc", "ai workstation", "local llm pc", "ml workstation"],
            target_profit_multiplier=1.08,
        )
        proposals_created += await _apply_rule_to_use_case(
            "gaming",
            trigger_score=score_gaming,
            threshold=4.0,
            marker="demand_rules_v1_gaming_pc",
            reason="Google Trends indicates gaming-PC intent; broaden gaming playbook search coverage.",
            keyword_add=["gaming pc", "custom gaming pc", "prebuilt gaming pc", "gaming desktop"],
            target_profit_multiplier=1.05,
        )
        proposals_created += await _apply_rule_to_use_case(
            "budget",
            trigger_score=score_budget,
            threshold=2.0,
            marker="demand_rules_v1_budget_gaming_pc",
            reason="Budget gaming search demand is rising; add low-cost gaming-intent terms to budget sourcing.",
            keyword_add=["budget gaming pc", "cheap gaming pc", "entry gaming pc"],
            target_profit_multiplier=1.04,
        )
        proposals_created += await _apply_rule_to_use_case(
            "workstation",
            trigger_score=score_workstation,
            threshold=2.0,
            marker="demand_rules_v1_workstation_pc",
            reason="Workstation search demand is rising; add workstation-intent terms to sourcing strategy.",
            keyword_add=["workstation pc", "cad workstation", "render workstation"],
            target_profit_multiplier=1.04,
        )

        # Demand-driven CREATE proposals for missing high-demand archetypes.
        active_use_cases = {str(pb.target_use_case or "").lower() for pb in playbooks}
        demand_map = {
            "Gaming PCs": "gaming",
            "Workstations": "workstation",
            "Office Clearance": "office",
            "HTPC / SFF": "htpc",
            "Budget Builders": "budget",
            "No-GPU Flips": "gaming",
        }
        for cat in demand_categories:
            if cat.get("strength") != "High":
                continue
            use_case = demand_map.get(cat.get("name", ""))
            if not use_case or use_case in active_use_cases:
                continue
            existing_pending_create = await db.execute(
                select(PlaybookProposal).where(
                    and_(
                        PlaybookProposal.action == "CREATE",
                        PlaybookProposal.status == "pending",
                    )
                )
            )
            pending = list(existing_pending_create.scalars().all())
            if any((p.proposed_data or {}).get("target_use_case") == use_case for p in pending):
                continue

            proposal = PlaybookProposal(
                action="CREATE",
                playbook_id=None,
                proposed_data={
                    "name": f"{cat['name']} Auto Playbook",
                    "emoji": "🧠",
                    "description": f"Auto-proposed from sustained {cat['strength']} demand in {cat['name']}.",
                    "status": "candidate",
                    "target_use_case": use_case,
                    "requirements": {},
                    "search_strategy": {"keywords": [], "listing_types": ["buy_it_now", "auction"]},
                    "upgrade_strategy": {"required": [], "optional": []},
                    "profit_strategy": {"target_margin_pct": 25, "target_profit_gbp": 90, "sell_platform": "eBay"},
                    "upsell_strategy": {"accessories": []},
                },
                reason=f"Demand engine detected sustained high demand in {cat['name']}; propose candidate playbook.",
                demand_signals={
                    "source": "demand_engine_v1",
                    "category": cat.get("name"),
                    "count": cat.get("count"),
                    "gem_count": cat.get("gem_count"),
                    "trend": cat.get("trend"),
                    "strength": cat.get("strength"),
                    "external_summary": external.get("summary", {}),
                },
                status="pending",
                proposed_at=datetime.utcnow(),
            )
            db.add(proposal)
            proposals_created += 1
            active_use_cases.add(use_case)

        if not sold_flips or not playbooks:
            await db.commit()
            return {"ok": True, "proposals_created": proposals_created, "playbooks_scored": playbooks_scored, "reason": "insufficient_sold_flip_data"}

        avg_profit = sum(float(f.actual_profit or 0.0) for f in sold_flips) / max(1, len(sold_flips))

        for pb in playbooks:
            strategy = dict(pb.profit_strategy or {})
            target_profit = float(strategy.get("target_profit_gbp") or 0.0)
            if target_profit <= 0:
                continue

            delta = avg_profit - target_profit
            # Only propose material change (>= ±12%)
            if abs(delta) / max(1.0, target_profit) < 0.12:
                continue

            # Skip if there is already a pending UPDATE proposal for this playbook
            existing_pending = await db.execute(
                select(PlaybookProposal).where(
                    and_(
                        PlaybookProposal.playbook_id == pb.id,
                        PlaybookProposal.action == "UPDATE",
                        PlaybookProposal.status == "pending",
                    )
                )
            )
            if existing_pending.scalar_one_or_none() is not None:
                continue

            if delta > 0:
                reason = "Sold-flip outcomes are outperforming current target; propose higher target to capture upside."
            else:
                reason = "Sold-flip outcomes are underperforming current target; propose conservative recalibration."

            variant = "A" if (pb.id % 2 == 0) else "B"
            if delta > 0:
                suggested = round(target_profit * (1.10 if variant == "A" else 1.07), 0)
            else:
                suggested = round(target_profit * (0.90 if variant == "A" else 0.93), 0)

            new_strategy = dict(strategy)
            new_strategy["target_profit_gbp"] = max(20.0, float(suggested))

            proposal = PlaybookProposal(
                action="UPDATE",
                playbook_id=pb.id,
                proposed_data={"profit_strategy": new_strategy},
                reason=reason,
                demand_signals={
                    "window_days": 30,
                    "sold_flips": len(sold_flips),
                    "avg_actual_profit": round(avg_profit, 2),
                    "old_target_profit": target_profit,
                    "suggested_target_profit": float(new_strategy["target_profit_gbp"]),
                    "source": "playbook_evolution_v1",
                    "ab_variant": variant,
                    "ab_hypothesis": "Variant A applies stronger target shift than Variant B.",
                },
                status="pending",
                proposed_at=datetime.utcnow(),
            )
            db.add(proposal)
            proposals_created += 1

        await db.commit()

    # Sync search terms from demand data
    terms_result = await _sync_search_terms(external, demand_categories)
    log.info("playbook_evolution.done",
             proposals_created=proposals_created,
             sold_flips=len(sold_flips),
             terms_upserted=terms_result.get("upserted", 0),
             terms_disabled=terms_result.get("disabled", 0))
    if proposals_created > 0:
        try:
            await emit_alert(
                code="demand_playbook_proposals_created",
                source="playbook_evolution",
                severity="info",
                message=(
                    f"Demand engine created {proposals_created} playbook proposal(s) "
                    f"from observed demand changes."
                ),
            )
        except Exception as exc:
            log.warning("playbook_evolution.alert_emit_error", error=str(exc))
    return {
        "ok": True,
        "proposals_created": proposals_created,
        "playbooks_scored": playbooks_scored,
        "sold_flips": len(sold_flips),
        "terms_upserted": terms_result.get("upserted", 0),
    }


# ── Static flip_opportunities terms (always present) ─────────────────────────
_FLIP_STATIC_TERMS = [
    {"term": "ex-workstation pc builds",  "group": "static"},
    {"term": "motherboard cpu combo",      "group": "static"},
    {"term": "HP pc",                      "group": "static"},
    {"term": "Lenovo pc",                  "group": "static"},
    {"term": "Dell pc",                    "group": "static"},
    {"term": "office pc",                  "group": "static"},
    {"term": "No GPU pc",                  "group": "static"},
    {"term": "No memory pc",               "group": "static"},
    {"term": "pc tower",                   "group": "static"},
    {"term": "gaming pc",                  "group": "static"},
    {"term": "desktop pc",                 "group": "static"},
]

# ── Static accessories terms (never auto-changed) ─────────────────────────────
_ACCESSORY_TERMS = [
    {"term": "gaming keyboard",            "group": "accessories"},
    {"term": "gaming mouse",               "group": "accessories"},
    {"term": "gaming headset",             "group": "accessories"},
    {"term": "gaming monitor",             "group": "accessories"},
    {"term": "gaming controller",          "group": "accessories"},
    {"term": "gaming speakers",            "group": "accessories"},
    {"term": "mechanical keyboard",        "group": "accessories"},
    {"term": "rgb keyboard",               "group": "accessories"},
    {"term": "wireless gaming mouse",      "group": "accessories"},
    {"term": "webcam streaming",           "group": "accessories"},
]

# Demand signal → additional search terms with score mapping.
# Keys are Google Trends query names; value = list of terms to upsert if score > threshold.
_DEMAND_TERM_RULES: list[dict] = [
    # Cases — driven by trending styles
    {"query": "panoramic case",      "scope": "cases", "group": "trending", "threshold": 2.0,
     "terms": ["panoramic pc case", "wraparound glass case", "fish tank pc case"]},
    {"query": "white pc build",      "scope": "cases", "group": "trending", "threshold": 2.0,
     "terms": ["white gaming case", "white airflow case", "white rgb case", "snow white pc case"]},
    {"query": "cyberpunk pc",        "scope": "cases", "group": "trending", "threshold": 2.0,
     "terms": ["cyberpunk pc case", "rgb cyberpunk case", "neon gaming case"]},
    {"query": "mini itx build",      "scope": "cases", "group": "trending", "threshold": 2.0,
     "terms": ["sff gaming case", "mini itx case", "compact gaming case"]},
    {"query": "streaming setup",     "scope": "cases", "group": "trending", "threshold": 2.0,
     "terms": ["streamer pc case", "content creator pc case", "streaming rgb setup"]},
    # Accessories
    {"query": "gaming keyboard",     "scope": "accessories", "group": "trending", "threshold": 3.0,
     "terms": ["mechanical gaming keyboard", "rgb gaming keyboard", "wireless gaming keyboard"]},
    {"query": "gaming monitor",      "scope": "accessories", "group": "trending", "threshold": 3.0,
     "terms": ["24 inch gaming monitor", "27 inch gaming monitor", "144hz monitor"]},
    # Flip opportunities
    {"query": "ai pc",               "scope": "flip_opportunities", "group": "ai", "threshold": 5.0,
     "terms": ["ai workstation pc", "local llm pc", "ml workstation"]},
    {"query": "budget gaming pc",    "scope": "flip_opportunities", "group": "budget", "threshold": 2.0,
     "terms": ["cheap gaming pc", "budget gaming desktop", "entry level gaming pc"]},
    # Upgrade parts
    {"query": "rtx 4060",            "scope": "upgrade_parts", "group": "gpu", "threshold": 3.0,
     "terms": ["RTX 4060", "RTX 4060 Ti"]},
    {"query": "rtx 4070",            "scope": "upgrade_parts", "group": "gpu", "threshold": 3.0,
     "terms": ["RTX 4070", "RTX 4070 Super"]},
]

_ZERO_RESULTS_DISABLE_THRESHOLD = 5  # disable after this many consecutive zero-result runs


async def _build_component_terms_from_playbooks(db) -> list[dict]:
    """Build generic component search terms from active playbook ideal_build fields."""
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(Playbook).where(Playbook.status == "active"))
    playbooks = result.scalars().all()

    terms: set[str] = set()
    always = [
        "i5 cpu", "i7 cpu", "i9 cpu", "ryzen cpu", "am4 cpu", "am5 cpu",
        "am4 motherboard", "am5 motherboard", "b450 motherboard", "b550 motherboard",
        "b650 motherboard", "x670 motherboard", "ddr4 ram", "ddr5 ram",
        "32gb ram", "rgb ram", "ddr5 rgb", "650w psu", "750w psu",
        "gaming psu", "nvidia gpu", "amd gpu", "rtx gpu", "radeon gpu",
        "cpu cooler", "aio cooler", "rgb cpu cooler", "rgb fans", "argb fans",
        "nvme ssd", "m.2 ssd",
    ]
    for t in always:
        terms.add(t)

    for pb in playbooks:
        ideal = pb.ideal_build or {}
        for component_key, comp_data in ideal.items():
            if component_key in ("case", "rgb_fans"):
                continue
            if not isinstance(comp_data, dict):
                continue
            for st in comp_data.get("search_terms", []):
                if st and len(st) > 3:
                    terms.add(str(st).strip().lower())

    return [{"term": t, "group": "components"} for t in sorted(terms)]


async def _build_case_terms_from_playbooks(db) -> list[dict]:
    """Build case search terms from active playbook ideal_build case preferences."""
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(Playbook).where(Playbook.status == "active"))
    playbooks = result.scalars().all()

    terms: set[str] = set()
    base_case_terms = [
        "gaming pc case", "atx gaming case", "rgb gaming case", "white gaming case",
        "tempered glass case", "fish tank case", "panoramic case", "argb case",
        "showcase case", "white pc case", "black rgb case", "micro atx case",
    ]
    for t in base_case_terms:
        terms.add(t)

    for pb in playbooks:
        ideal = pb.ideal_build or {}
        case_data = ideal.get("case", {})
        if isinstance(case_data, dict):
            for st in case_data.get("search_terms", []):
                if st and len(st) > 3:
                    terms.add(str(st).strip().lower())

    return [{"term": t, "group": "cases"} for t in sorted(terms)]


async def _sync_search_terms(external: dict, demand_categories: list) -> dict:
    """
    Sync search terms per catalogue spec:
    - flip_opportunities: static terms + 5 dynamic terms from demand data
    - components: generic terms derived from active playbook ideal_builds
    - cases: derived from active playbook case preferences
    - accessories: static
    """
    signal_map = _latest_query_signal_map(external)
    upserted = 0
    disabled = 0

    all_sources = [
        "eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions",
        "Amazon", "Gumtree", "Temu", "AliExpress", "Alibaba",
        "BargainHardware", "CherryTree Inc", "Preloved",
    ]

    async with AsyncSessionLocal() as db:
        component_terms = await _build_component_terms_from_playbooks(db)
        case_terms = await _build_case_terms_from_playbooks(db)

        # ── Generate 5 dynamic flip_opportunities terms ───────────────────────
        sorted_cats = sorted(demand_categories, key=lambda c: c.get("count", 0), reverse=True)
        _CAT_TO_FLIP_TERMS: dict[str, list[str]] = {
            "Gaming PCs": ["gaming pc", "rtx gaming desktop", "custom gaming build"],
            "Workstations": ["hp workstation", "dell workstation", "ex workstation pc"],
            "Budget Builders": ["budget gaming pc", "no gpu gaming pc", "cheap gaming desktop"],
            "Office Clearance": ["office clearance pc", "ex office desktop pc"],
            "HTPC / SFF": ["mini pc gaming", "small form factor gaming pc"],
        }
        dynamic_terms: list[str] = []
        for cat in sorted_cats:
            if len(dynamic_terms) >= 5:
                break
            candidates = _CAT_TO_FLIP_TERMS.get(cat.get("name", ""), [])
            for t in candidates:
                if t not in dynamic_terms:
                    dynamic_terms.append(t)
                    if len(dynamic_terms) >= 5:
                        break

        # Supplement with Google Trends if needed
        trend_map = {
            "budget gaming pc": "budget gaming pc desktop",
            "ai pc": "AI workstation desktop",
            "white pc build": "white RGB gaming PC",
            "rtx 3070": "RTX 3070 gaming PC build",
            "gaming pc": "gaming pc desktop tower",
        }
        for query, term in trend_map.items():
            if len(dynamic_terms) >= 5:
                break
            if _score_for(signal_map, query) >= 2.0 and term not in dynamic_terms:
                dynamic_terms.append(term)

        # Fallback to ensure exactly 5
        fallback = ["AM5 gaming PC", "RTX 4060 gaming desktop", "Ryzen 7 gaming PC",
                    "mini ITX gaming PC", "white RGB gaming PC"]
        for fb in fallback:
            if len(dynamic_terms) >= 5:
                break
            if fb not in dynamic_terms:
                dynamic_terms.append(fb)

        dynamic_term_dicts = [{"term": t, "group": "dynamic"} for t in dynamic_terms[:5]]

        # ── Upsert all terms ───────────────────────────────────────────────────
        catalogue_terms: dict[str, list[dict]] = {
            "flip_opportunities": _FLIP_STATIC_TERMS + dynamic_term_dicts,
            "components": component_terms,
            "cases": case_terms,
            "accessories": _ACCESSORY_TERMS,
        }

        for scope, terms in catalogue_terms.items():
            for entry in terms:
                term_text = entry["term"]
                is_baseline = entry.get("group") not in ("dynamic",)
                result = await db.execute(
                    select(SourceSearchTerm).where(
                        SourceSearchTerm.scope == scope,
                        SourceSearchTerm.term == term_text,
                    )
                )
                row = result.scalar_one_or_none()
                if row is None:
                    db.add(SourceSearchTerm(
                        scope=scope,
                        group_name=entry.get("group", "baseline"),
                        term=term_text,
                        source_names=all_sources,
                        notes="auto_baseline" if is_baseline else "dynamic",
                        enabled=True,
                        is_baseline=is_baseline,
                        demand_score=5.0,
                    ))
                    upserted += 1
                else:
                    row.enabled = True
                    if is_baseline:
                        row.is_baseline = True
                    if row.demand_score == 0.0:
                        row.demand_score = 5.0

        # ── Auto-disable dead non-baseline terms ───────────────────────────────
        dead_result = await db.execute(
            select(SourceSearchTerm).where(
                SourceSearchTerm.is_baseline == False,  # noqa: E712
                SourceSearchTerm.enabled == True,       # noqa: E712
                SourceSearchTerm.zero_results_streak >= _ZERO_RESULTS_DISABLE_THRESHOLD,
            )
        )
        for dead in dead_result.scalars().all():
            dead.enabled = False
            disabled += 1
            log.info("search_term.auto_disabled",
                     term=dead.term, scope=dead.scope,
                     streak=dead.zero_results_streak)

        await db.commit()

    log.info("search_terms.synced", upserted=upserted, disabled=disabled,
             dynamic_flip_terms=dynamic_terms[:5])
    return {"upserted": upserted, "disabled": disabled, "dynamic_flip_terms": dynamic_terms[:5]}
