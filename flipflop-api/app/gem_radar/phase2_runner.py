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

from app.gem_radar.cpk_market import get_robust_active_market, get_robust_sold_market
from app.gem_radar.demand_velocity import record_demand_snapshot, calculate_watch_velocity, calculate_bid_velocity
from app.gem_radar.opportunity_scoring import load_opportunity_policy, score_opportunity
from app.gem_radar.favourite_matching import find_matching_favourite
from app.gem_radar.marketplace import fallback_listing_url
from app.models.favourite import Favourite
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_intelligence import GemRadarDecisionEvent, PreferredComponent
from app.services.alerts import emit_alert
from app.services.ebay_catalog import get_product_reviews

SEARCH_RUN_ID = "cpk-phase2-classify"


@dataclass
class Phase2Result:
    total_cpk_tagged: int
    classified_count: int
    unsettled_count: int
    classification_counts: dict[str, int] = field(default_factory=dict)


async def run_phase2_classification(db: AsyncSession) -> Phase2Result:
    policy = await load_opportunity_policy(db)

    result = await db.execute(
        text(
            """
            SELECT DISTINCT ON (lo.listing_id)
                lo.listing_id, lo.title, lo.seller_name, lo.image_url,
                lo.condition_normalised AS condition, lo.item_price, lo.postage_price,
                lo.delivered_price, lo.source, lo.observed_at,
                cpk.cpk, cpk.cpk_data, lo.bid_count, lo.watch_count,
                lo.epid, lo.seller_feedback_percent, lo.seller_feedback_count
            FROM gem_radar_listing_observations lo
            JOIN gem_radar_listing_cpk cpk ON lo.listing_id = cpk.listing_id
            ORDER BY lo.listing_id, lo.observed_at DESC, lo.id DESC
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

        market = await get_robust_sold_market(
            db, cpk=cpk, condition=condition, subject_listing_id=listing_id, policy=policy
        )
        preliminary_market = False
        if market is None:
            market = await get_robust_sold_market(
                db, cpk=cpk, condition=condition, subject_listing_id=listing_id,
                policy=policy, minimum_comps=3,
            )
            preliminary_market = market is not None
            if market is None:
                market = await get_robust_active_market(
                    db, cpk=cpk, condition=condition,
                    subject_listing_id=listing_id, policy=policy,
                )
                preliminary_market = False
                if market is None:
                    unsettled_count += 1
        category = (cpk_data or {}).get("category")

        # Record demand snapshot for velocity tracking (Phase 2 enhancement).
        await record_demand_snapshot(
            db, listing_id, SEARCH_RUN_ID,
            watch_count, bid_count, delivered_price
        )

        cohort_counts = (await db.execute(text("""
            SELECT
              (SELECT COUNT(DISTINCT COALESCE(source_url, id::text)) FROM gem_radar_sold_observations
               WHERE cpk = :cpk AND LOWER(condition) = :condition
                 AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '90 days') AS sold_count,
              (SELECT COUNT(*) FROM gem_radar_cpk_listing_price
               WHERE cpk = :cpk AND listing_id <> :listing_id
                 AND updated_at >= CURRENT_TIMESTAMP - INTERVAL '14 days') AS active_count
        """), {"cpk": cpk, "condition": "new" if (condition or "").lower() == "new" else "used", "listing_id": listing_id})).one()
        preferred = (await db.execute(select(PreferredComponent).where(PreferredComponent.component_key == cpk))).scalar_one_or_none() is not None
        opportunity = score_opportunity(
            listing_price=delivered_price, title=title, cpk_data=cpk_data,
            market=market, sold_count_90d=int(cohort_counts[0] or 0), active_count=int(cohort_counts[1] or 0),
            watch_velocity=await calculate_watch_velocity(db, listing_id),
            bid_velocity=await calculate_bid_velocity(db, listing_id),
            policy=policy, preferred=preferred,
            extra_risk_flags=("preliminary_sold_cohort",) if preliminary_market else (),
            listing_condition=condition,
        )
        classification = opportunity.classification
        deal_score = opportunity.score / 10.0
        adjusted_confidence = market.confidence if market else 0.0
        recommendation = "BUY_NOW" if opportunity.decision == "BUY_NOW" else ("OFFER_DEAL" if opportunity.decision == "MAKE_OFFER" else "DO_NOT_BUY")

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

        decision = opportunity.decision

        # The scored table is the latest-current decision surface, not an
        # event ledger. A live ingestion pathway may have written this
        # listing after the run-level cleanup began, so replace it here too;
        # history remains in GemRadarDecisionEvent and observation tables.
        await db.execute(
            text("DELETE FROM gem_radar_scored_listings WHERE listing_id = :listing_id"),
            {"listing_id": listing_id},
        )
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
            expected_profit=opportunity.expected_profit,
            roi_pct=opportunity.roi_pct,
            walk_away_price=opportunity.walk_away_price,
            conservative_resale_price=market.conservative_resale if market else None,
            market_confidence=market.confidence if market else 0.0,
            market_sample_size=market.sample_size if market else 0,
            market_source_diversity=market.source_diversity if market else 0,
            market_spread_pct=market.spread_pct if market else None,
            liquidity_score=opportunity.liquidity_score,
            desirability_score=opportunity.desirability_score,
            risk_score=opportunity.risk_score,
            eligible=opportunity.eligible,
            scoring_explanation=opportunity.explanation(),
            reasoning_summary=" ".join(opportunity.reasons),
            listing_observed_at=observed_at,
        )
        db.add(db_row)
        await db.flush()

        # Active BIN / retail-new observations are context only and are
        # refreshed by their dedicated ingestion jobs. A bulk rescore must
        # never fan out one external API request per listing or let those
        # asking prices leak into realised resale value.

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
                "lower": market.lower if market else None,
                "median": market.median if market else None,
                "upper": market.upper if market else None,
                "offset": round((delivered_price - market.conservative_resale) / market.conservative_resale * 100, 2) if market and market.conservative_resale else None,
                "recommendation": recommendation,
                "cpk": cpk,
                "id": db_row.id,
            },
        )

        classified_count += 1
        classification_counts[classification] = classification_counts.get(classification, 0) + 1

        db.add(GemRadarDecisionEvent(
            listing_id=listing_id, classification=classification, decision=decision,
            score=opportunity.score, explanation=opportunity.explanation(),
        ))

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
