"""
Scheduled markdown/sale-event candidate scan — Algorithm Playbook row 46.

Distinct from the small price-refresh nudge (row 6, folded into the recreate
cycle) and the sold-comp price-decay engine (rows 19-20): eBay's native
Promotions Manager runs a real, time-boxed percentage-discount event. Per the
implementation plan, this is NOT fully unattended — a price cut visible to
buyers is a real decision, so this job only identifies opted-in candidates
(markdown_event_opt_in=True, unsold after 2 recreate cycles) and raises an
alert for one-click admin confirmation, rather than firing the discount
itself. Default proposed, confirm once: candidate threshold = 2 recreate
cycles unsold (~14-16 days); default discount = 15%.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select

from app.services.alerts import emit_alert

log = structlog.get_logger(__name__)

CANDIDATE_RECREATE_CYCLES = 2
DEFAULT_DISCOUNT_PCT = 0.15


async def run_markdown_event_scan_job() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.flip import Flip, FlipStage

    flagged = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Flip).where(
                Flip.stage == FlipStage.ready_for_sale,
                Flip.markdown_event_opt_in.is_(True),
                Flip.recreate_cycle_count >= CANDIDATE_RECREATE_CYCLES,
            )
        )
        candidates = result.scalars().all()

        for flip in candidates:
            flagged += 1
            try:
                await emit_alert(
                    code="markdown_event_candidate",
                    source="markdown_event",
                    severity="info",
                    message=(
                        f"Flip #{flip.id} has gone {flip.recreate_cycle_count} recreate cycles "
                        f"unsold and is opted into markdown events — confirm a "
                        f"{DEFAULT_DISCOUNT_PCT * 100:.0f}% Promotions Manager sale event to run it."
                    ),
                )
            except Exception as exc:
                log.warning("markdown_event.alert_failed", flip_id=flip.id, error=str(exc))

    return {"flagged": flagged}


async def run_manual_build_markdown_event_scan_job() -> dict:
    """ManualBuild equivalent — see module docstring. Candidate condition is
    status == 'listed' (already live, still unsold) rather than Flip's
    ready_for_sale, since ManualBuild has an explicit listed stage."""
    from app.database import AsyncSessionLocal
    from app.models.manual_build import ManualBuild

    flagged = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManualBuild).where(
                ManualBuild.status == "listed",
                ManualBuild.markdown_event_opt_in.is_(True),
                ManualBuild.recreate_cycle_count >= CANDIDATE_RECREATE_CYCLES,
            )
        )
        candidates = result.scalars().all()

        for build in candidates:
            flagged += 1
            try:
                await emit_alert(
                    code="markdown_event_candidate",
                    source="markdown_event",
                    severity="info",
                    message=(
                        f"Build #{build.id} ({build.name}) has gone {build.recreate_cycle_count} recreate "
                        f"cycles unsold and is opted into markdown events — confirm a "
                        f"{DEFAULT_DISCOUNT_PCT * 100:.0f}% Promotions Manager sale event to run it."
                    ),
                )
            except Exception as exc:
                log.warning("markdown_event.manual_build_alert_failed", build_id=build.id, error=str(exc))

    return {"flagged": flagged}
