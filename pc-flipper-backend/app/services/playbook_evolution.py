from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import and_, select

from app.database import AsyncSessionLocal
from app.models.flip import Flip, FlipStage
from app.models.playbook import Playbook, PlaybookProposal
from app.services.demand_service import compute_demand
from app.services.external_demand import latest_external_signal_snapshot

log = structlog.get_logger(__name__)


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
        external = await latest_external_signal_snapshot(limit_per_source=15)
        proposals_created = 0

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
    return {"ok": True, "proposals_created": proposals_created, "sold_flips": len(sold_flips)}
