from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.alert_event import AlertEvent
from app.models.warranty import WarrantyReserve
from app.services.warranty_service import (
    lock_warranty_owner_then_reserve,
    recalculate_reserve_status,
)


async def run_warranty_reserve_job() -> dict:
    """Mark elapsed, claim-free reserves eligible and notify the operator.

    This worker never releases funds. It locks the owning order/build before
    the reserve, matching claim and release paths. Release remains an explicit,
    audited admin action.
    """
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        reserve_ids = (await db.execute(
            select(WarrantyReserve.id).where(
                WarrantyReserve.warranty_expires_at <= now,
                WarrantyReserve.status != "released",
            )
        )).scalars().all()
        alert_count = 0
        expired_checked = 0
        for reserve_id in reserve_ids:
            reserve = await lock_warranty_owner_then_reserve(
                db,
                reserve_id,
                skip_locked=True,
            )
            if (
                reserve is None
                or reserve.status == "released"
                or reserve.warranty_expires_at > now
            ):
                continue
            expired_checked += 1
            await recalculate_reserve_status(db, reserve, now=now)
            if reserve.status == "eligible_for_release" and reserve.expiry_alerted_at is None:
                reserve.expiry_alerted_at = datetime.utcnow()
                amount = round(max(0.0, reserve.reserved_amount_gbp - reserve.allocated_claim_amount_gbp), 2)
                db.add(AlertEvent(
                    code=f"warranty_reserve_eligible_{reserve.id}",
                    source="warranty",
                    severity="info",
                    message=f"Warranty reserve {reserve.id} is eligible for reviewed release (£{amount:.2f}).",
                    link_url="/warranty-reserves",
                ))
                alert_count += 1
        # Eligibility and its one-time admin alert share a transaction. If
        # either write fails, both roll back and the next scheduled run retries.
        await db.commit()

    return {"ok": True, "eligible_alerts": alert_count, "expired_checked": expired_checked}
