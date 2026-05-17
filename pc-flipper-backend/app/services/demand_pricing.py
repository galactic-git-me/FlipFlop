from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_demand_signal import ExternalDemandSignal
from app.models.listing import Listing, ListingStatus


async def compute_demand_pricing_multipliers(db: AsyncSession) -> dict:
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=14)

    # Internal listing momentum (last 14d)
    internal_rows = await db.execute(
        select(Listing)
        .where(
            and_(
                Listing.status == ListingStatus.active,
                Listing.first_seen_at >= recent_cutoff,
            )
        )
    )
    listings = list(internal_rows.scalars().all())

    gpu_count = sum(1 for l in listings if (l.gpu or "").strip())
    cpu_count = sum(1 for l in listings if (l.cpu or "").strip())
    ram_count = sum(1 for l in listings if (l.ram_gb or 0) > 0)
    board_count = sum(1 for l in listings if "motherboard" in (l.title or "").lower())

    # External signal strength (last 7d)
    ext_cutoff = now - timedelta(days=7)
    ext_rows = await db.execute(
        select(
            ExternalDemandSignal.topic,
            func.avg(ExternalDemandSignal.score),
            func.avg(ExternalDemandSignal.confidence),
        )
        .where(ExternalDemandSignal.signal_time >= ext_cutoff)
        .group_by(ExternalDemandSignal.topic)
    )

    topic_strength: dict[str, float] = {}
    for topic, avg_score, avg_conf in ext_rows.all():
        s = float(avg_score or 0.0)
        c = float(avg_conf or 0.0)
        topic_strength[topic] = s * (0.5 + (c * 0.5))

    am5_strength = topic_strength.get("am5_bundles", 0.0)
    gpu_strength = topic_strength.get("midrange_gpu", 0.0)
    cpu_strength = topic_strength.get("workstation_cpu", 0.0)

    # Convert signal to multiplier in bounded range [0.88, 1.25]
    def _bounded(x: float) -> float:
        return max(0.88, min(1.25, x))

    # Blend internal activity + external pulse
    gpu_mult = _bounded(1.0 + ((gpu_count / 80.0) * 0.08) + (gpu_strength / 100.0) * 0.15)
    cpu_mult = _bounded(1.0 + ((cpu_count / 80.0) * 0.07) + (cpu_strength / 100.0) * 0.16)
    ram_mult = _bounded(1.0 + ((ram_count / 120.0) * 0.04) + (am5_strength / 100.0) * 0.08)
    motherboard_mult = _bounded(1.0 + ((board_count / 60.0) * 0.05) + (am5_strength / 100.0) * 0.18)

    return {
        "window_days": 14,
        "external_window_days": 7,
        "internal_counts": {
            "gpu": gpu_count,
            "cpu": cpu_count,
            "ram": ram_count,
            "motherboard": board_count,
        },
        "external_topic_strength": {
            "am5_bundles": round(am5_strength, 2),
            "midrange_gpu": round(gpu_strength, 2),
            "workstation_cpu": round(cpu_strength, 2),
        },
        "multipliers": {
            "gpu_midrange": round(gpu_mult, 3),
            "cpu_workstation": round(cpu_mult, 3),
            "ram_ddr5": round(ram_mult, 3),
            "motherboard_am5": round(motherboard_mult, 3),
        },
    }
