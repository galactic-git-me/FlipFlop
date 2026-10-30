"""Reconcile ManualBuild listing state with eBay's authoritative APIs."""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from app.models.manual_build import ManualBuild

log = structlog.get_logger(__name__)


def classify_ebay_listing_state(
    remote: dict | None,
    *,
    order_found: bool,
    confirmed_unavailable: bool = False,
) -> str:
    """Pure lifecycle decision used by reconciliation and unit tests."""
    remote_status = str((remote or {}).get("listing_status") or "").lower()
    quantity_sold = int((remote or {}).get("quantity_sold") or 0)
    if remote_status in {"active", "started"}:
        return "active"
    if order_found or quantity_sold > 0:
        return "sold"
    if confirmed_unavailable:
        return "missing"
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
    if not str(build.ebay_listing_id).isdecimal():
        # Trading API GetItem and Fulfillment legacyItemId lookups require
        # eBay's numeric legacy listing ID; placeholder/local IDs are not live listings.
        build.ebay_listing_status = "unknown"
        build.ebay_listing_status_checked_at = datetime.utcnow()
        log.info("manual_build.ebay_listing_check_skipped", build_id=build.id, reason="invalid_legacy_item_id")
        await db.flush()
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
    from app.services.ebay_trading_api import EbayTradingApiError, get_item_status

    settings = get_settings()
    target_environment = environment or settings.ebay_listing_environment
    try:
        token = access_token or await get_valid_ebay_access_token(target_environment, db=db)
    except ValueError:
        build.ebay_listing_status = "unknown"
        build.ebay_listing_status_checked_at = datetime.utcnow()
        log.info("manual_build.ebay_listing_check_skipped", build_id=build.id, reason="seller_oauth_unavailable")
        await db.flush()
        return build.ebay_listing_status
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
        order_lookup_failed = False
        try:
            order = await find_order_for_listing(
                build.ebay_listing_id,
                environment=target_environment,
                lookback_days=90,
                db=db,
            )
        except EbayOrderSyncError as exc:
            order_lookup_failed = True
            log.warning("manual_build.ebay_order_reconcile_failed", build_id=build.id, error=str(exc))
        # Error 17 means this seller cannot access the old item. After eBay's
        # order lookup succeeds and finds no sale, let the relist cycle create
        # a fresh listing with a new ID. Network/auth errors remain unknown.
        confirmed_unavailable = (
            not order_lookup_failed
            and isinstance(remote_error, EbayTradingApiError)
            and "17" in remote_error.error_codes
        )
        state = classify_ebay_listing_state(
            remote,
            order_found=order is not None,
            confirmed_unavailable=confirmed_unavailable,
        )
        if confirmed_unavailable and state == "missing":
            log.info(
                "manual_build.ebay_listing_missing_confirmed",
                build_id=build.id,
                listing_id=build.ebay_listing_id,
                next_action="create_new_listing",
            )
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
        from app.services.getting_started_jobs import ensure_manual_build_job
        await ensure_manual_build_job(db, manual_build_id=build.id)
        from app.services.inventory_lifecycle import record_sale
        from app.services.cross_channel_guard import withdraw_storefront_for_sold_build
        await record_sale(db, build, build.sale_price_actual)
        if build.warranty_started_at or build.delivered_at:
            from app.services.warranty_service import ensure_manual_build_reserve, recalculate_reserve_status
            reserve = await ensure_manual_build_reserve(
                db, build, build.warranty_started_at or build.delivered_at
            )
            if reserve is not None:
                await recalculate_reserve_status(db, reserve)
        await withdraw_storefront_for_sold_build(build, db)
    elif state in {"ended", "missing"}:
        if build.status == "listed":
            build.status = "built"
        build.ebay_listing_end_reason = "ended_early" if state == "ended" else "missing_from_ebay"
    elif remote_error is not None:
        build.ebay_listing_end_reason = None
    await db.flush()
    return state
