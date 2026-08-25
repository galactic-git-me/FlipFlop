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

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar.cpk_market import robust_active_market
from app.gem_radar.demand_velocity import record_demand_snapshot
from app.gem_radar.opportunity_scoring import OpportunityResult, SoldComparable, identity_gates, load_opportunity_policy, risk_safety_score, robust_sold_market, score_opportunity
from app.gem_radar.favourite_matching import find_matching_favourite
from app.gem_radar.marketplace import fallback_listing_url
from app.models.favourite import Favourite
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_intelligence import GemRadarDecisionEvent, PreferredComponent
from app.models.price_alert import PriceAlert, PriceAlertEvent
from app.gem_radar.identity import resolve_identity
from app.services.alerts import emit_alert
from app.services.ebay_catalog import get_product_reviews

SEARCH_RUN_ID = "cpk-phase2-classify"


@dataclass
class Phase2Result:
    total_cpk_tagged: int
    classified_count: int
    unsettled_count: int
    classification_counts: dict[str, int] = field(default_factory=dict)


async def run_phase2_classification(db: AsyncSession, *, enrich_product_reviews: bool = True) -> Phase2Result:
    policy = await load_opportunity_policy(db)

    result = await db.execute(
        text(
            """
            SELECT DISTINCT ON (lo.listing_id)
                lo.listing_id, lo.title, lo.seller_name, lo.image_url,
                lo.condition_normalised AS condition, lo.item_price, lo.postage_price,
                lo.delivered_price, lo.source, lo.observed_at,
                cpk.cpk, cpk.cpk_data, lo.category AS observed_category, lo.bid_count, lo.watch_count,
                lo.epid, lo.seller_feedback_percent, lo.seller_feedback_count
            FROM gem_radar_listing_observations lo
            LEFT JOIN gem_radar_listing_cpk cpk ON lo.listing_id = cpk.listing_id
            ORDER BY lo.listing_id, lo.observed_at DESC, lo.id DESC
            """
        )
    )
    listings = result.fetchall()

    sold_rows = (await db.execute(text("""
        SELECT cpk, LOWER(condition), price, postage, source_url,
               EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - observed_at)) / 86400.0
        FROM gem_radar_sold_observations
        WHERE cpk IS NOT NULL
          AND observed_at >= CURRENT_TIMESTAMP - make_interval(days => :lookback)
          AND price > 0
    """), {"lookback": policy.sold_lookback_days})).all()
    sold_cohorts: dict[tuple[str, str], list[SoldComparable]] = defaultdict(list)
    for sold_cpk, sold_condition, sold_price, sold_postage, sold_url, sold_days in sold_rows:
        sold_cohorts[(sold_cpk, "new" if sold_condition == "new" else "used")].append(
            SoldComparable(float(sold_price), float(sold_postage or 0), sold_url, float(sold_days or 0))
        )

    # One bulk read for all fresh active cohorts. Re-querying the observation
    # join once per listing made a full rebuild O(listings × database roundtrip).
    active_rows = (await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (listing_id) listing_id, title, condition_normalised, source
            FROM gem_radar_listing_observations
            ORDER BY listing_id, observed_at DESC, id DESC
        )
        SELECT p.cpk, p.listing_id, p.price, l.source,
               CASE WHEN LOWER(l.title) ~ '\\m(b[ -]?grade|open[ -]?box|refurbished|renewed)\\M' THEN 'used'
                    WHEN LOWER(COALESCE(l.condition_normalised, '')) = 'new' THEN 'new' ELSE 'used' END condition
        FROM gem_radar_cpk_listing_price p
        JOIN latest l ON l.listing_id = p.listing_id
        WHERE p.updated_at >= CURRENT_TIMESTAMP - INTERVAL '14 days' AND p.price > 0
    """))).all()
    active_cohorts: dict[tuple[str, str], list[SoldComparable]] = defaultdict(list)
    for active_cpk, active_listing_id, active_price, active_source, active_condition in active_rows:
        active_cohorts[(active_cpk, active_condition)].append(
            SoldComparable(float(active_price), source_url=f"{active_source or 'active'}://{active_listing_id}")
        )

    velocity_rows = (await db.execute(text("""
        SELECT listing_id,
          CASE WHEN COUNT(watch_count) >= 2 AND EXTRACT(EPOCH FROM (MAX(observed_at)-MIN(observed_at))) > 0
            THEN GREATEST(0, (MAX(watch_count)-MIN(watch_count)) /
              (EXTRACT(EPOCH FROM (MAX(observed_at)-MIN(observed_at))) / 3600.0)) END watch_velocity,
          CASE WHEN COUNT(bid_count) >= 2 AND EXTRACT(EPOCH FROM (MAX(observed_at)-MIN(observed_at))) > 0
            THEN GREATEST(0, (MAX(bid_count)-MIN(bid_count)) /
              (EXTRACT(EPOCH FROM (MAX(observed_at)-MIN(observed_at))) / 3600.0)) END bid_velocity
        FROM gem_radar_listing_demand_history
        WHERE observed_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
        GROUP BY listing_id
    """))).all()
    velocities = {row[0]: (float(row[1]) if row[1] is not None else None, float(row[2]) if row[2] is not None else None) for row in velocity_rows}

    favourites = (await db.execute(select(Favourite))).scalars().all()
    preferred_keys = set((await db.execute(select(PreferredComponent.component_key))).scalars().all())
    component_price_alerts = (await db.execute(select(PriceAlert).where(
        PriceAlert.alert_type == "component",
        PriceAlert.is_active.is_(True),
        PriceAlert.triggered_at.is_(None),
    ))).scalars().all()
    existing_reviews = {
        listing_id: (average, count)
        for listing_id, average, count in (
            await db.execute(
                select(
                    GemRadarScoredListing.listing_id,
                    GemRadarScoredListing.review_average_rating,
                    GemRadarScoredListing.review_count,
                )
            )
        ).all()
        if average is not None or count is not None
    }

    await db.execute(text("DELETE FROM gem_radar_scored_listings WHERE search_run_id = :run_id"), {"run_id": SEARCH_RUN_ID})

    classified_count = 0
    unsettled_count = 0
    classification_counts: dict[str, int] = {}

    for row in listings:
        (
            listing_id, title, seller_name, image_url, condition,
            item_price, postage_price, delivered_price, source, observed_at,
            cpk, cpk_data, observed_category, bid_count, watch_count,
            epid, seller_feedback_percent, seller_feedback_count,
        ) = row

        title_condition = (title or "").lower()
        title_marks_non_new = any(term in title_condition for term in ("b grade", "b-grade", "open box", "open-box", "refurbished", "renewed"))
        normalised_condition = "new" if (condition or "").lower() == "new" and not title_marks_non_new else "used"
        category = (cpk_data or {}).get("category") or observed_category
        sold_comps = sold_cohorts.get((cpk, normalised_condition), [])
        market = robust_sold_market(sold_comps, subject_listing_id=listing_id, policy=policy) if cpk else None
        preliminary_market = False
        if not cpk:
            unsettled_count += 1
        if cpk and market is None:
            market = robust_sold_market(
                sold_comps, subject_listing_id=listing_id,
                policy=replace(policy, minimum_sold_comps=3),
            )
            preliminary_market = market is not None
            if market is None:
                market = robust_active_market(
                    active_cohorts.get((cpk, normalised_condition), []),
                    condition=normalised_condition, subject_listing_id=listing_id,
                    policy=policy,
                )
                preliminary_market = False
                if market is None:
                    unsettled_count += 1

        # Record demand snapshot for velocity tracking (Phase 2 enhancement).
        await record_demand_snapshot(
            db, listing_id, SEARCH_RUN_ID,
            watch_count, bid_count, delivered_price
        )
        title_key = re.sub(r"[^a-z0-9]", "", (title or "").lower())
        for alert in component_price_alerts:
            identity = resolve_identity(alert.component_key or "")
            model = identity.model or alert.component_key or ""
            model_key = re.sub(r"[^a-z0-9]", "", model.lower())
            if not model_key or model_key not in title_key:
                # Marketplace titles commonly omit manufacturer/family words;
                # accept the distinctive CPU/GPU model token as the fallback.
                token = re.search(r"\b(?:RTX|GTX|RX)?\s*\d{3,5}(?:X3D|XTX|SUPER|TI|XT|X|G|KF|K|F)?\b", model, re.IGNORECASE)
                token_key = re.sub(r"[^a-z0-9]", "", token.group(0).lower()) if token else ""
                if not token_key or token_key not in title_key:
                    continue
            if market is not None:
                alert.market_reference_price_gbp = round(float(market.median) * 100)
                alert.target_price_gbp = round(float(market.median) * (1 - (alert.discount_threshold_pct or 15) / 100) * 100)
            current_pennies = round(float(delivered_price) * 100)
            if current_pennies <= alert.target_price_gbp:
                alert.triggered_at = datetime.utcnow()
                alert.triggered_price_gbp = current_pennies
                db.add(PriceAlertEvent(
                    alert_id=alert.id,
                    event_type="triggered",
                    price_gbp=current_pennies,
                    notes=f"{title} reached at least {alert.discount_threshold_pct or 15:.0f}% below its market reference",
                ))

        sold_count = len({_source.source_url or f"price:{_source.delivered_price}" for _source in sold_comps})
        active_count = max(0, len(active_cohorts.get((cpk, normalised_condition), [])) - 1)
        preferred = cpk in preferred_keys
        watch_velocity, bid_velocity = velocities.get(listing_id, (None, None))
        if cpk:
            opportunity = score_opportunity(
                listing_price=delivered_price, title=title, cpk_data=cpk_data,
                market=market, sold_count_90d=sold_count, active_count=active_count,
                watch_velocity=watch_velocity, bid_velocity=bid_velocity,
                policy=policy, preferred=preferred,
                extra_risk_flags=("preliminary_sold_cohort",) if preliminary_market else (),
                listing_condition=condition,
            )
        else:
            pending_identity = {"category": category, "brand": None, "model": None}
            flags = identity_gates(title, pending_identity)
            hard_vetoes = [flag for flag in flags if flag != "identity_incomplete"]
            classification = "INELIGIBLE" if hard_vetoes else ("IDENTITY_PENDING" if category else "IDENTITY_FAILED")
            decision = "IGNORE" if hard_vetoes else "INVESTIGATE"
            opportunity = OpportunityResult(
                classification=classification, decision=decision, score=0.0,
                expected_profit=None, roi_pct=None, walk_away_price=None,
                liquidity_score=None, desirability_score=None,
                risk_score=risk_safety_score(flags), market=None,
                eligible=False,
                reasons=["Listing was processed, but no trustworthy canonical product identity is available."],
                risk_flags=flags,
            )
        classification = opportunity.classification
        deal_score = opportunity.score / 10.0
        adjusted_confidence = market.confidence if market else 0.0
        recommendation = "BUY_NOW" if opportunity.decision == "BUY_NOW" else ("OFFER_DEAL" if opportunity.decision == "MAKE_OFFER" else "DO_NOT_BUY")

        # Product review rating is a per-epid external API call (7-day
        # cached, see services/ebay_catalog.py) — only worth paying for on
        # the tier the user actually acts on. OK_DEAL/AVERAGE_DEAL/POOR_DEAL
        # listings never fetch it.
        review_average_rating, review_count = existing_reviews.get(listing_id, (None, None))
        if enrich_product_reviews and classification in ("GEM", "SUPER_GEM") and epid:
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
            # Legacy column name; now stores the selected operational resale
            # basis (median). market_lower_price retains the downside value.
            conservative_resale_price=market.median if market else None,
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
                "offset": round((delivered_price - market.median) / market.median * 100, 2) if market and market.median else None,
                "recommendation": recommendation,
                "cpk": cpk,
                "id": db_row.id,
            },
        )

        classified_count += 1
        classification_counts[classification] = classification_counts.get(classification, 0) + 1

        latest_decision = (
            await db.execute(
                select(GemRadarDecisionEvent)
                .where(GemRadarDecisionEvent.listing_id == listing_id)
                .order_by(GemRadarDecisionEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if (
            latest_decision is None
            or latest_decision.classification != classification
            or latest_decision.decision != decision
            or abs(latest_decision.score - opportunity.score) >= 0.01
            or datetime.utcnow() - latest_decision.created_at >= timedelta(hours=24)
        ):
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
