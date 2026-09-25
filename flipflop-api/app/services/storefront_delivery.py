"""Delivery options shared by storefront checkout and server-side pricing."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings


def add_working_days(start: datetime, days: int) -> datetime:
    current = start
    remaining = max(0, days)
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


async def load_delivery_settings(db: AsyncSession) -> AppSettings:
    settings = (await db.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one_or_none()
    if settings:
        return settings
    settings = AppSettings(name="default")
    db.add(settings)
    await db.flush()
    return settings


async def delivery_choice(db: AsyncSession, fulfilment_type: str, speedy: bool) -> dict:
    settings = await load_delivery_settings(db)
    now = datetime.now(ZoneInfo("Europe/London"))
    speedy_fee = float(settings.speedy_delivery_price_gbp if settings.speedy_delivery_price_gbp is not None else 49.0) if speedy else 0.0
    if fulfilment_type == "prebuilt":
        if speedy:
            cutoff_hour = int(settings.speedy_prebuilt_cutoff_hour if settings.speedy_prebuilt_cutoff_hour is not None else 14)
            before_cutoff = (now.hour, now.minute) < (cutoff_hour, 0)
            cutoff = f"{cutoff_hour:02d}:00"
            promise = f"Same-day dispatch when ordered before {cutoff} UK time; orders after the cutoff dispatch the next working day."
            return {"fulfilment_type": fulfilment_type, "speedy_delivery": True, "fee_gbp": speedy_fee,
                    "promise": promise, "delivery_days": None, "same_day_dispatch": before_cutoff}
        days = int(settings.standard_prebuilt_days if settings.standard_prebuilt_days is not None else 3)
        return {"fulfilment_type": fulfilment_type, "speedy_delivery": False, "fee_gbp": 0.0,
                "promise": f"Estimated delivery within {days} working days.", "delivery_days": days, "same_day_dispatch": False}

    days = int(settings.speedy_curated_custom_days if settings.speedy_curated_custom_days is not None else 3) if speedy else int(settings.standard_curated_custom_days if settings.standard_curated_custom_days is not None else 5)
    return {"fulfilment_type": fulfilment_type, "speedy_delivery": speedy, "fee_gbp": speedy_fee,
            "promise": f"Estimated delivery within {days} working days.", "delivery_days": days, "same_day_dispatch": False}


def checkout_metadata(choice: dict) -> dict[str, str]:
    return {
        "delivery_type": str(choice["fulfilment_type"]),
        "speedy_delivery": "true" if choice["speedy_delivery"] else "false",
        "delivery_fee_gbp": f"{float(choice['fee_gbp']):.2f}",
        "delivery_promise": str(choice["promise"]),
        "delivery_days": "" if choice["delivery_days"] is None else str(choice["delivery_days"]),
        "same_day_dispatch": "true" if choice["same_day_dispatch"] else "false",
    }
