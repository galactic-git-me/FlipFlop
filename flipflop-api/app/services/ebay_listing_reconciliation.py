"""Reconcile ManualBuild listing state with eBay's authoritative APIs."""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from app.models.manual_build import ManualBuild

log = structlog.get_logger(__name__)


def classify_ebay_listing_state(remote: dict | None, *, order_found: bool) -> str:
    """Pure lifecycle decision used by reconciliation and unit tests."""
    remote_status = str((remote or {}).get("listing_status") or "").lower()
    quantity_sold = int((remote or {}).get("quantity_sold") or 0)
    if remote_status in {"active", "started"}:
        return "active"
    if order_found or quantity_sold > 0:
        return "sold"
    if remote_status in {"completed", "ended"}:
        return "ended"
    if remote is not None:
        return "missing"
    return "unknown"


async def reconcile_manual_build_listing(
    build: ManualBuild,
    db,
    *,
    force: bool = False,
    access_token: str | None = None,
    environment: str | None = None,
) -> str:
    """Return active/sold/ended/missing/never_listed/unknown.

    A network or authentication failure is deliberately `unknown`: it must
    never authorize creation of a duplicate listing.
    """
    if not build.ebay_listing_id:
        build.ebay_listing_status = "never_listed"
        build.ebay_listing_status_checked_at = datetime.utcnow()
        return build.ebay_listing_status
    if (
        not force
        and build.ebay_listing_status_checked_at
        and build.ebay_listing_status_checked_at >= datetime.utcnow() - timedelta(seconds=60)
    ):
        return build.ebay_listing_status or "unknown"

    from app.config import get_settings
    from app.services.ebay_order_sync import find_order_for_listing, EbayOrderSyncError
    from app.services.ebay_token_manager import get_valid_ebay_access_token
    from app.services.ebay_trading_api import get_item_status

    settings = get_settings()
    target_environment = environment or settings.ebay_listing_environment
    token = access_token or await get_valid_ebay_access_token(target_environment)
    checked_at = datetime.utcnow()
    remote: dict | None = None
    remote_error: Exception | None = None
    try:
        remote = await get_item_status(build.ebay_listing_id, token, target_environment)
    except Exception as exc:
        remote_error = exc
        log.warning(
            "manual_build.ebay_get_item_failed",
            build_id=build.id,
            listing_id=build.ebay_listing_id,
            error=str(exc),
        )

    remote_status = str((remote or {}).get("listing_status") or "").lower()
    if remote_status in {"active", "started"}:
        state = classify_ebay_listing_state(remote, order_found=False)
    else:
        # A completed/vanished listing is sold only when eBay's order API or
        # QuantitySold proves it. Mere disappearance is an early/manual end.
        order = None
        try:
            order = await find_order_for_listing(
                build.ebay_listing_id,
                environment=target_environment,
                lookback_days=90,
            )
        except EbayOrderSyncError as exc:
            log.warning("manual_build.ebay_order_reconcile_failed", build_id=build.id, error=str(exc))
        state = classify_ebay_listing_state(remote, order_found=order is not None)
        if state == "sold":
            if order is not None:
                build.ebay_order_id = order.order_id
                build.sale_price_actual = order.sale_price

    build.ebay_listing_status = state
    build.ebay_listing_status_checked_at = checked_at
    if state == "active":
        build.status = "listed"
        build.ebay_listing_end_reason = None
    elif state == "sold":
        build.status = "sold"
        build.ebay_listing_end_reason = "sold"
        from app.services.inventory_lifecycle import record_sale
        from app.services.cross_channel_guard import withdraw_storefront_for_sold_build
        await record_sale(db, build, build.sale_price_actual)
        await withdraw_storefront_for_sold_build(build, db)
    elif state in {"ended", "missing"}:
        if build.status == "listed":
            build.status = "built"
        build.ebay_listing_end_reason = "ended_early" if state == "ended" else "missing_from_ebay"
    elif remote_error is not None:
        build.ebay_listing_end_reason = None
    await db.flush()
    return state
