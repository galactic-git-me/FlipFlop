from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import and_, select

from app.database import AsyncSessionLocal
from app.models.flip import Flip, FlipStage
from app.models.playbook import Playbook, PlaybookProposal
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
            return {"ok": True, "proposals_created": proposals_created, "reason": "insufficient_sold_flip_data"}

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

    log.info("playbook_evolution.done", proposals_created=proposals_created, sold_flips=len(sold_flips))
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
        except Exception:
            pass
    return {"ok": True, "proposals_created": proposals_created, "sold_flips": len(sold_flips)}
