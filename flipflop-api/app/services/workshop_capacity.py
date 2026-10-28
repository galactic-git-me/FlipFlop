"""Capacity ledger helpers for admin quote assessments and short holds."""
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce_evidence import WorkshopCapacityEvidence, WorkshopCapacityReservation


async def lock_build_week(db: AsyncSession, build_week: str) -> None:
    """Serialize all capacity writes for one ISO week in Postgres."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:build_week), 90928)"),
        {"build_week": build_week},
    )


async def latest_capacity_evidence(db: AsyncSession, build_week: str) -> WorkshopCapacityEvidence | None:
    result = await db.execute(
        select(WorkshopCapacityEvidence)
        .where(WorkshopCapacityEvidence.build_week == build_week)
        .order_by(WorkshopCapacityEvidence.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def active_hold_count(db: AsyncSession, build_week: str, now: datetime) -> int:
    result = await db.execute(
        select(func.count(WorkshopCapacityReservation.id)).where(
            WorkshopCapacityReservation.build_week == build_week,
            WorkshopCapacityReservation.status == "held",
            WorkshopCapacityReservation.expires_at > now,
        )
    )
    return int(result.scalar_one())


def capacity_evidence_is_current(evidence: WorkshopCapacityEvidence, now: datetime) -> bool:
    age_seconds = (now - evidence.observed_at).total_seconds()
    current = now.astimezone(timezone.utc).date().isocalendar()
    year, week = evidence.build_week.split("-W", maxsplit=1)
    return (
        0 <= age_seconds <= 24 * 60 * 60
        and (int(year), int(week)) >= (current.year, current.week)
    )
