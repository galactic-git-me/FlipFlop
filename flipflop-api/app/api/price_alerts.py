"""Admin API for creating and managing build price alerts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ManualBuild, PriceAlert
from app.routes.admin_auth import get_current_admin
from app.services.money import Money
from app.services.price_alerts import PriceAlertError, PriceAlertsService
from app.services.feature_flags import FeatureFlags, is_enabled
from app.services.email_service import smtp_is_configured

router = APIRouter(prefix="/price-alerts", tags=["price-alerts"], dependencies=[Depends(get_current_admin)])


class CreatePriceAlert(BaseModel):
    manual_build_id: int
    user_email: EmailStr
    target_price_gbp: float = Field(gt=0)


def _out(alert: PriceAlert, build: ManualBuild | None) -> dict:
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
        "cpk": alert.cpk,
        "condition_cohort": alert.condition_cohort,
        "monitoring_status": alert.monitoring_status,
        "market_reference_price_gbp": alert.market_reference_price_gbp / 100 if alert.market_reference_price_gbp is not None else None,
        "reference_basis": alert.reference_basis,
        "discount_threshold_pct": alert.discount_threshold_pct,
        "user_email": alert.user_email,
        "target_price_gbp": alert.target_price_gbp / 100 if alert.target_price_gbp is not None else None,
        "is_active": alert.is_active,
        "triggered_at": alert.triggered_at,
        "triggered_price_gbp": alert.triggered_price_gbp / 100 if alert.triggered_price_gbp is not None else None,
        "listing_url": alert.triggered_listing_url if is_component else build.ebay_listing_url if build else None,
        "reference_evidence": alert.reference_evidence_json,
        "triggered_evidence": alert.triggered_evidence_json,
        "last_evaluated_at": alert.last_evaluated_at,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


@router.get("")
async def list_price_alerts(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceAlert, ManualBuild)
        .outerjoin(ManualBuild, ManualBuild.id == PriceAlert.manual_build_id)
        .where(or_(PriceAlert.owner_admin_id == admin.id, PriceAlert.user_email == admin.email))
        .order_by(PriceAlert.created_at.desc())
    )
    items = [_out(alert, build) for alert, build in result.all()]
    return {
        "items": items,
        "active_count": sum(1 for item in items if item["monitoring_status"] == "armed"),
        "pending_count": sum(1 for item in items if item["monitoring_status"].startswith("pending_")),
        "triggered_count": sum(1 for item in items if item["monitoring_status"] == "triggered"),
        "rules_enabled": is_enabled(FeatureFlags.PRICE_ALERTS_RULES_ENABLED),
        "email_enabled": is_enabled(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED) and is_enabled(FeatureFlags.EMAIL_DISPATCH_ENABLED),
        "smtp_configured": smtp_is_configured(),
    }


@router.post("", status_code=201)
async def create_price_alert(body: CreatePriceAlert, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    try:
        alert = await PriceAlertsService.create_alert(
            db, body.manual_build_id, admin.email, Money(body.target_price_gbp, "GBP")
        )
    except PriceAlertError as exc:
        raise HTTPException(400, str(exc)) from exc
    build = await db.get(ManualBuild, alert.manual_build_id)
    alert.owner_admin_id = admin.id
    await db.commit()
    return _out(alert, build)


@router.post("/{alert_id}/dismiss")
async def dismiss_price_alert(alert_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    alert = await db.get(PriceAlert, alert_id)
    if not alert or (alert.owner_admin_id not in (None, admin.id) and alert.user_email != admin.email):
        raise HTTPException(404, "Price alert not found")
    if not await PriceAlertsService.dismiss_alert(db, alert_id):
        raise HTTPException(404, "Price alert not found")
    return {"ok": True}


@router.post("/{alert_id}/re-arm")
async def rearm_price_alert(alert_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    alert = await db.get(PriceAlert, alert_id)
    if not alert or (alert.owner_admin_id not in (None, admin.id) and alert.user_email != admin.email):
        raise HTTPException(404, "Price alert not found")
    if not await PriceAlertsService.re_arm_alert(db, alert_id):
        raise HTTPException(404, "Price alert not found")
    return {"ok": True}


@router.get("/{alert_id}/history")
async def price_alert_history(alert_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    alert = await db.get(PriceAlert, alert_id)
    if not alert or (alert.owner_admin_id not in (None, admin.id) and alert.user_email != admin.email):
        raise HTTPException(404, "Price alert not found")
    events = await PriceAlertsService.get_alert_history(db, alert_id)
    return {"items": [{
        "id": event.id,
        "event_type": event.event_type,
        "price_gbp": event.price_gbp / 100 if event.price_gbp is not None else None,
        "notes": event.notes,
        "created_at": event.created_at,
    } for event in events]}
