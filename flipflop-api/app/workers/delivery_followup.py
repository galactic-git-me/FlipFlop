"""Durable post-delivery customer follow-up worker."""
from datetime import datetime
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.manual_build import ManualBuild
from app.services.email_service import send_delivery_followup_email


async def run_delivery_followup_job() -> dict:
    sent = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(ManualBuild).where(ManualBuild.delivered_at.is_not(None), ManualBuild.customer_email.is_not(None), ManualBuild.delivery_followup_sent_at.is_(None)))).scalars().all()
        for build in rows:
            ok = await send_delivery_followup_email(build.customer_email, build.buyer_name or "there", build.id, review_url=f"https://theflipflop.shop/reviews.html?build={build.id}")
            if ok:
                build.delivery_followup_sent_at = datetime.utcnow()
                sent += 1
        await db.commit()
    return {"sent": sent}
