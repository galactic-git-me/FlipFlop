"""Admin API for creating and managing build price alerts."""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.gem_radar.identity import resolve_identity
from app.gem_radar.marketplace import fallback_listing_url
from app.models import GemRadarScoredListing, ManualBuild, PriceAlert
from app.services.money import Money
from app.services.price_alerts import PriceAlertError, PriceAlertsService

router = APIRouter(prefix="/price-alerts", tags=["price-alerts"])


class CreatePriceAlert(BaseModel):
    manual_build_id: int
    user_email: EmailStr
    target_price_gbp: float = Field(gt=0)


def _out(alert: PriceAlert, build: ManualBuild | None, current_listing_url: str | None = None) -> dict:
    is_component = alert.alert_type == "component"
    return {
        "id": alert.id,
        "manual_build_id": alert.manual_build_id,
        "build_name": alert.component_key if is_component else build.name if build else f"Build {alert.manual_build_id}",
        "build_status": "preferred component" if is_component else build.status if build else None,
        "current_price_gbp": (alert.market_reference_price_gbp / 100 if alert.market_reference_price_gbp is not None else None) if is_component else (build.ebay_price or build.total_cost) if build else None,
        "alert_type": alert.alert_type,
        "component_key": alert.component_key,
        "component_slot": alert.component_slot,
        "market_reference_price_gbp": alert.market_reference_price_gbp / 100 if alert.market_reference_price_gbp is not None else None,
        "discount_threshold_pct": alert.discount_threshold_pct,
        "user_email": alert.user_email,
        "target_price_gbp": alert.target_price_gbp / 100,
        "is_active": alert.is_active,
        "triggered_at": alert.triggered_at,
        "triggered_price_gbp": alert.triggered_price_gbp / 100 if alert.triggered_price_gbp is not None else None,
        "listing_url": (alert.triggered_listing_url or current_listing_url) if is_component else build.ebay_listing_url if build else None,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


@router.get("")
async def list_price_alerts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceAlert, ManualBuild)
        .outerjoin(ManualBuild, ManualBuild.id == PriceAlert.manual_build_id)
        .order_by(PriceAlert.created_at.desc())
    )
    alert_rows = result.all()
    component_alerts = [alert for alert, _ in alert_rows if alert.alert_type == "component" and not alert.triggered_listing_url]
    current_urls: dict[int, str] = {}
    if component_alerts:
        scored = (await db.execute(select(GemRadarScoredListing))).scalars().all()
        for alert in component_alerts:
            wanted_category = alert.component_slot or resolve_identity(alert.component_key or "").category
            wanted_terms = {
                term for term in re.findall(r"[a-z0-9]+", (alert.component_key or "").lower())
                if len(term) >= 3 and term not in {"the", "with", "white", "black", "iridescent", "chassis"}
            }
            candidates: list[tuple[int, float, GemRadarScoredListing]] = []
            for listing in scored:
                listing_identity = resolve_identity(listing.title or "")
                if wanted_category and listing_identity.category != wanted_category:
                    continue
                title_terms = set(re.findall(r"[a-z0-9]+", (listing.title or "").lower()))
                overlap = len(wanted_terms & title_terms)
                # Require the brand/model wording to agree strongly enough to
                # avoid linking RAM alerts to enclosures or CPU alerts to boards.
                if overlap < min(2, len(wanted_terms)):
                    continue
                candidates.append((overlap, float(listing.delivered_price), listing))
            if candidates:
                _, _, best = min(candidates, key=lambda item: (-item[0], item[1]))
                url = best.url or fallback_listing_url(best.listing_id, best.source, best.title)
                if url:
                    current_urls[alert.id] = url
    items = [_out(alert, build, current_urls.get(alert.id)) for alert, build in alert_rows]
    return {
        "items": items,
        "active_count": sum(1 for item in items if item["is_active"]),
        "triggered_count": sum(1 for item in items if item["triggered_at"] is not None and item["is_active"]),
    }


@router.post("", status_code=201)
async def create_price_alert(body: CreatePriceAlert, db: AsyncSession = Depends(get_db)):
    try:
        alert = await PriceAlertsService.create_alert(
            db, body.manual_build_id, body.user_email, Money(body.target_price_gbp, "GBP")
        )
    except PriceAlertError as exc:
        raise HTTPException(400, str(exc)) from exc
    build = await db.get(ManualBuild, alert.manual_build_id)
    return _out(alert, build)


@router.post("/{alert_id}/dismiss")
async def dismiss_price_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    if not await PriceAlertsService.dismiss_alert(db, alert_id):
        raise HTTPException(404, "Price alert not found")
    return {"ok": True}


@router.post("/{alert_id}/re-arm")
async def rearm_price_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    if not await PriceAlertsService.re_arm_alert(db, alert_id):
        raise HTTPException(404, "Price alert not found")
    return {"ok": True}


@router.get("/{alert_id}/history")
async def price_alert_history(alert_id: int, db: AsyncSession = Depends(get_db)):
    if not await db.get(PriceAlert, alert_id):
        raise HTTPException(404, "Price alert not found")
    events = await PriceAlertsService.get_alert_history(db, alert_id)
    return {"items": [{
        "id": event.id,
        "event_type": event.event_type,
        "price_gbp": event.price_gbp / 100 if event.price_gbp is not None else None,
        "notes": event.notes,
        "created_at": event.created_at,
    } for event in events]}
