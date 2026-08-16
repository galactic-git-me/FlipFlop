"""Phase 2 of the CPK-driven market-price system: classify every CPK-tagged
listing purely from its % offset against a settled CPK market price (see
app/gem_radar/cpk_market.py and deal_classification.py) — no LLM, no
external benchmarks, no outlier filtering.

Run automatically by the queue processor once a scan sweep signals
completion (see app/api/gem_radar.py's /scan-sweep-complete endpoint and
app/workers/queue_processor.py's _phase2_trigger_loop) — never call this
mid-ingestion, since a market price only means anything once every listing
in the current sweep has had a chance to contribute to it.

scripts/phase2_classify_by_market_price.py is a thin CLI wrapper around
run_phase2_classification for manual/offline re-runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar.cpk_market import get_market_price_with_hierarchy_fallback
from app.gem_radar.deal_classification import (
    classify_by_offset,
    deal_score_from_offset,
    load_deal_thresholds,
    market_price_for_source,
    pct_offset,
    recommendation_for_classification,
)
from app.gem_radar.demand_velocity import record_demand_snapshot, detect_hot_item
from app.gem_radar.favourite_matching import find_matching_favourite
from app.gem_radar.marketplace import fallback_listing_url
from app.models.favourite import Favourite
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.services.alerts import emit_alert
from app.services.ebay_browse import get_component_prices
from app.services.ebay_catalog import get_product_reviews

SEARCH_RUN_ID = "cpk-phase2-classify"


@dataclass
class Phase2Result:
    total_cpk_tagged: int
    classified_count: int
    unsettled_count: int
    classification_counts: dict[str, int] = field(default_factory=dict)


async def run_phase2_classification(db: AsyncSession) -> Phase2Result:
    thresholds = await load_deal_thresholds(db)

    result = await db.execute(
        text(
            """
            SELECT
                lo.listing_id, lo.title, lo.seller_name, lo.image_url,
                lo.condition_normalised AS condition, lo.item_price, lo.postage_price,
                lo.delivered_price, lo.source, lo.observed_at,
                cpk.cpk, cpk.cpk_data, lo.bid_count, lo.watch_count,
                lo.epid, lo.seller_feedback_percent, lo.seller_feedback_count
            FROM gem_radar_listing_observations lo
            JOIN gem_radar_listing_cpk cpk ON lo.listing_id = cpk.listing_id
            ORDER BY lo.listing_id
            """
        )
    )
    listings = result.fetchall()

    favourites = (await db.execute(select(Favourite))).scalars().all()

    await db.execute(text("DELETE FROM gem_radar_scored_listings WHERE search_run_id = :run_id"), {"run_id": SEARCH_RUN_ID})

    classified_count = 0
    unsettled_count = 0
    classification_counts: dict[str, int] = {}

    for row in listings:
        (
            listing_id, title, seller_name, image_url, condition,
            item_price, postage_price, delivered_price, source, observed_at,
            cpk, cpk_data, bid_count, watch_count,
            epid, seller_feedback_percent, seller_feedback_count,
        ) = row

        market = await get_market_price_with_hierarchy_fallback(db, cpk)
        if market is None:
            unsettled_count += 1
            continue

        market_price = market_price_for_source(market, thresholds.market_price_source)
        offset = pct_offset(delivered_price, market_price)
        classification = classify_by_offset(offset, thresholds)
        deal_score = deal_score_from_offset(offset, thresholds)
        recommendation = recommendation_for_classification(classification)
        category = (cpk_data or {}).get("category")

        # Record demand snapshot for velocity tracking (Phase 2 enhancement).
        await record_demand_snapshot(
            db, listing_id, SEARCH_RUN_ID,
            watch_count or 0, bid_count or 0, delivered_price
        )

        # Demand signal multiplier for GEM/SUPER_GEM listings.
        # High watch count + high bid count = real demand signal (boost confidence).
        # High watch count + low/zero bid count = price-likely-too-high signal (reduce confidence).
        # Hot items (watch/bid velocity > threshold) get an additional boost.
        # This is a weak signal (not a veto) — real price competitiveness matters more.
        demand_multiplier = 1.0
        if classification in ("GEM", "SUPER_GEM"):
            watch_count = watch_count or 0
            bid_count = bid_count or 0
            if watch_count > 5 and bid_count > 1:
                demand_multiplier = 1.15  # +15% confidence boost
            elif watch_count > 20 and bid_count <= 1:
                demand_multiplier = 0.85  # -15% confidence reduction

            # Check for hot-item velocity signals (growing watch/bid counts).
            is_hot = await detect_hot_item(db, listing_id)
            if is_hot:
                demand_multiplier *= 1.15  # Additional +15% for velocity

        base_confidence = min(100.0, market.listing_count * 20.0)
        adjusted_confidence = min(100.0, base_confidence * demand_multiplier)

        # Product review rating is a per-epid external API call (7-day
        # cached, see services/ebay_catalog.py) — only worth paying for on
        # the tier the user actually acts on. OK_DEAL/AVERAGE_DEAL/POOR_DEAL
        # listings never fetch it.
        review_average_rating: float | None = None
        review_count: int | None = None
        if classification in ("GEM", "SUPER_GEM") and epid:
            reviews = await get_product_reviews(epid)
            review_average_rating = reviews.average_rating
            review_count = reviews.review_count

        decision_map = {
            "BUY_NOW_NO_QUESTION": "BUY_NOW",
            "BUY_NOW": "BUY_NOW",
            "OFFER_DEAL": "MAKE_OFFER",
            "DO_NOT_BUY": "IGNORE",
        }
        decision = decision_map.get(recommendation, "WATCH")

        db_row = GemRadarScoredListing(
            listing_id=listing_id,
            search_run_id=SEARCH_RUN_ID,
            source=source,
            url=fallback_listing_url(listing_id, source, title),
            title=title,
            seller_name=seller_name,
            image_url=image_url,
            condition=condition,
            category=category,
            epid=epid,
            seller_feedback_percent=seller_feedback_percent,
            seller_feedback_count=seller_feedback_count,
            review_average_rating=review_average_rating,
            review_count=review_count,
            actual_listing_price=item_price,
            postage_price=postage_price,
            delivered_price=delivered_price,
            bid_count=bid_count,
            watch_count=watch_count,
            classification=classification,
            deal_score=deal_score,
            confidence_score=adjusted_confidence,
            confidence_band="high" if adjusted_confidence >= 75 else ("medium" if adjusted_confidence >= 40 else "low"),
            decision=decision,
            listing_observed_at=observed_at,
        )
        db.add(db_row)
        await db.flush()

        try:
            market_prices = await get_component_prices(title, min_price=15.0)
            db_row.market_new_price = market_prices.get("new_min")
            db_row.market_used_price = market_prices.get("used_median")
        except Exception:
            pass

        # market_lower/median/upper_price, pct_offset, recommendation, cpk
        # aren't declared on the ORM model (added via a raw ALTER — see
        # scripts/setup_deal_classification_schema.py) so set them directly.
        await db.execute(
            text(
                """
                UPDATE gem_radar_scored_listings
                SET market_lower_price = :lower,
                    market_median_price = :median,
                    market_upper_price = :upper,
                    pct_offset = :offset,
                    recommendation = :recommendation,
                    cpk = :cpk
                WHERE id = :id
                """
            ),
            {
                "lower": market.min_price,
                "median": market.median_price,
                "upper": market.max_price,
                "offset": offset,
                "recommendation": recommendation,
                "cpk": cpk,
                "id": db_row.id,
            },
        )

        classified_count += 1
        classification_counts[classification] = classification_counts.get(classification, 0) + 1

        if classification in ("GEM", "SUPER_GEM") and favourites:
            matched_fav = find_matching_favourite(title, cpk, favourites)
            if matched_fav and listing_id not in matched_fav.matched_listing_ids:
                query_display = matched_fav.cpk if matched_fav.cpk else f"'{matched_fav.term}'"
                await emit_alert(
                    code="favourite_gem_match",
                    source="phase2_runner",
                    severity="info",
                    message=f"{classification}: {title} matches favourite {query_display} — £{delivered_price:.2f}",
                    link_url=f"/sourcing?listing={listing_id}",
                )
                matched_fav.matched_listing_ids = [*matched_fav.matched_listing_ids, listing_id]
                matched_fav.last_matched_at = datetime.utcnow()
                db.add(matched_fav)

    await db.commit()

    return Phase2Result(
        total_cpk_tagged=len(listings),
        classified_count=classified_count,
        unsettled_count=unsettled_count,
        classification_counts=classification_counts,
    )
