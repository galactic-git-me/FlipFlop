"""Reconcile ManualBuild listing state with eBay's authoritative APIs."""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select

from app.models.manual_build import ManualBuild

log = structlog.get_logger(__name__)


def classify_ebay_listing_state(
    remote: dict | None,
    *,
    order_found: bool,
    confirmed_unavailable: bool = False,
    cancelled_order: bool = False,
    reviewed_refund: bool = False,
) -> str:
    """Pure lifecycle decision used by reconciliation and unit tests."""
    remote_status = str((remote or {}).get("listing_status") or "").lower()
    quantity_sold = 0 if cancelled_order else int((remote or {}).get("quantity_sold") or 0)
    if order_found:
        return "sold"
    if reviewed_refund:
        return "ended"
    if remote_status in {"active", "started"}:
        return "active"
    if quantity_sold > 0:
        return "sold"
    if confirmed_unavailable:
        return "missing"
    if remote_status in {"completed", "ended"}:
        return "ended"
    if remote is not None:
        return "missing"
    return "unknown"


async def get_reviewed_refund_decision(db, build: ManualBuild) -> str | None:
    """Return the owner's current decision for this build's latest refund event."""
    if not build.ebay_order_id:
        return None
    from app.models.channel_listing import ChannelListing
    from app.models.listing_publish_event import ListingPublishEvent

    events = (await db.execute(
        select(ListingPublishEvent)
        .join(ChannelListing, ListingPublishEvent.channel_listing_id == ChannelListing.id)
        .where(
            ChannelListing.manual_build_id == build.id,
            ListingPublishEvent.event_type.in_(("refund_detected", "refund_relist_decision")),
        )
        .order_by(ListingPublishEvent.id.asc())
    )).scalars().all()
    latest_refund_id = None
    decisions: dict[int, str] = {}
    for event in events:
        metadata = event.event_metadata or {}
        if metadata.get("order_id") != build.ebay_order_id:
            continue
        if event.event_type == "refund_detected":
            latest_refund_id = event.id
        elif event.event_type == "refund_relist_decision":
            refund_event_id = metadata.get("refund_event_id")
            if isinstance(refund_event_id, int):
                decisions[refund_event_id] = str(metadata.get("decision") or "")
    decision = decisions.get(latest_refund_id)
    return decision if decision in {"relist", "keep_offline"} else None


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

    # A confirmed sale remains authoritative until a *new* eBay listing is
    # discovered after an eBay sale. An active original offer can be stale
    # because cross-channel withdrawal failed; the same offer is not proof
    # that the sold physical unit has returned to stock.
    if build.status == "sold" and build.ebay_listing_status == "sold" and build.ebay_sku:
        try:
            from app.services.ebay_token_manager import get_valid_ebay_access_token
            from app.config import get_settings
            from app.services.ebay_relisted_listing import find_active_listing_for_sku
            settings = get_settings()
            env = environment or settings.ebay_listing_environment
            token = access_token or await get_valid_ebay_access_token(env, db=db)
            active = await find_active_listing_for_sku(build.ebay_sku, token, env)
            if active and str(active["listing_id"]) != str(build.ebay_listing_id):
                from app.services.channel_sync import record_relisted_channel
                await record_relisted_channel(db, build, channel="ebay_uk",
                    external_listing_id=active["listing_id"], listing_url=active["listing_url"],
                    source="ebay_inventory_api")
                return "active"
            if active:
                log.info("manual_build.ebay_relist_ignored", build_id=build.id,
                    listing_id=active["listing_id"], reason="matches_sold_listing")
        except Exception as exc:
            log.warning("manual_build.ebay_relist_discovery_failed", build_id=build.id, error=str(exc))
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
    cancelled_order = False
    reviewed_refund_decision = await get_reviewed_refund_decision(db, build)
    reviewed_refund = False
    if build.ebay_order_id:
        from app.services.ebay_order_sync import get_order_refund_state, is_terminal_order_cancellation
        try:
            lifecycle = await get_order_refund_state(build.ebay_order_id,
                environment=target_environment, db=db)
            cancelled_order = is_terminal_order_cancellation(lifecycle)
        except EbayOrderSyncError as exc:
            log.warning("manual_build.ebay_cancel_state_check_failed", build_id=build.id, error=str(exc))
    if remote_status in {"active", "started"} and not cancelled_order and not reviewed_refund_decision:
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
            log.warning(
                "manual_build.ebay_order_reconcile_failed",
                build_id=build.id,
                error=str(exc),
            )
        if cancelled_order and order is not None:
            if order.order_id == build.ebay_order_id:
                # The API's paid-order search can still return a cancelled
                # order. Ignore that historical sale while preserving the
                # chance to recognize a later, distinct order for this item.
                order = None
            else:
                cancelled_order = False
        if reviewed_refund_decision and (
            order is None or order.order_id == build.ebay_order_id
        ):
            # The saved order is the refunded sale already reviewed by the
            # owner. Its old listing quantity must not recreate that sale,
            # even if eBay no longer returns the refunded order in search.
            order = None
            reviewed_refund = True
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
            cancelled_order=cancelled_order,
            reviewed_refund=reviewed_refund,
        )
        newly_recorded_order = order is not None and build.ebay_order_id != order.order_id
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
        # Remote activity informs withdrawal workers, but never restores a
        # confirmed physical unit to stock. Only record_relisted_channel,
        # after a distinct replacement listing is discovered, can do that.
        build.ebay_listing_end_reason = None
        if build.status == "built":
            build.status = "listed"
    elif state == "sold":
        build.status = "sold"
        build.ebay_listing_end_reason = "sold"
        if order is not None:
            build.ebay_order_id = order.order_id
            build.sale_price_actual = order.sale_price
            if newly_recorded_order:
                build.dispatch_status = "awaiting_dispatch"
            from app.models.app_settings import AppSettings
            from app.services.channel_sync import record_confirmed_sale
            settings_row = (await db.execute(
                select(AppSettings).where(AppSettings.name == "default")
            )).scalar_one_or_none()
            await record_confirmed_sale(
                db,
                build,
                channel="ebay_uk",
                order_id=order.order_id,
                sale_price=order.sale_price,
                source="ebay_fulfillment_order_api",
                account=settings_row.ebay_seller_username if settings_row else None,
            )
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
        if reviewed_refund:
            build.ebay_listing_end_reason = "refund_reviewed"
        else:
            build.ebay_listing_end_reason = "ended_early" if state == "ended" else "missing_from_ebay"
    elif remote_error is not None:
        build.ebay_listing_end_reason = None
    if cancelled_order:
        from app.models.channel_listing import ChannelListing
        from app.models.listing_publish_event import ListingPublishEvent
        from app.services.inventory_lifecycle import record_sale_cancellation
        dispatched = build.dispatch_status in {"dispatched", "delivered"}
        prior_cancel = (await db.execute(select(ListingPublishEvent).where(
            ListingPublishEvent.event_type == "ebay_order_cancelled",
            ListingPublishEvent.event_metadata["build_id"].as_integer() == build.id,
            ListingPublishEvent.event_metadata["order_id"].as_string() == build.ebay_order_id,
        ).limit(1))).scalar_one_or_none()
        channel_row = (await db.execute(select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id,
            ChannelListing.channel.in_(("ebay_uk", "ebay")),
        ).order_by(ChannelListing.id.desc()).limit(1))).scalars().first()
        if channel_row is None:
            channel_row = ChannelListing(manual_build_id=build.id, channel="ebay_uk",
                status="ended", external_listing_id=build.ebay_listing_id,
                listing_url=build.ebay_listing_url)
            db.add(channel_row)
            await db.flush()
        channel_row.status = "published" if state == "active" else "ended"
        if not prior_cancel:
            db.add(ListingPublishEvent(channel_listing_id=channel_row.id,
                event_type="ebay_order_cancelled",
                message=("eBay confirmed cancellation after dispatch; owner review is required." if dispatched
                    else "eBay confirmed cancellation; the unsent build is available for review."),
                event_metadata={"build_id": build.id, "order_id": build.ebay_order_id,
                    "cancel_state": "CANCELED", "source": "ebay_order_api",
                    "dispatch_status": build.dispatch_status}))
        if not dispatched:
            build.status = "listed" if state == "active" else "built"
            build.ebay_listing_end_reason = None if state == "active" else "order_cancelled"
            await record_sale_cancellation(db, build, source="ebay_order_api")
    await db.flush()
    return state
