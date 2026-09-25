"""Reconcile Gem Radar availability after a completed marketplace sweep."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar.observations import get_consecutive_misses_before_inactive


async def reconcile_listing_lifecycle(db: AsyncSession) -> dict[str, int]:
    """Archive exact sold items and listings missed by later completed scans.

    A listing is compared only with later scans of its own search term and
    vendor. Three unseen days are a fallback for sources whose run identity
    changes or stops being recorded. A fresh sighting restores the listing.
    """
    misses = max(1, await get_consecutive_misses_before_inactive(db))
    await db.execute(text("""
        INSERT INTO gem_radar_listing_lifecycle
            (listing_id, status, archive_reason, last_seen_at, archived_at, updated_at)
        WITH latest AS (
            SELECT DISTINCT ON (listing_id)
                listing_id, search_query, source, observed_at,
                CASE WHEN source = 'ebay'
                     THEN substring(listing_id FROM '(?i)(?:ebay:|%2f|/)([0-9]{9,14})')
                END AS ebay_item_id
            FROM gem_radar_listing_observations
            ORDER BY listing_id, observed_at DESC, id DESC
        ), expanded_runs AS (
            SELECT r.search_term, vendor.source, r.occurred_at
            FROM gem_radar_scan_runs r
            CROSS JOIN LATERAL jsonb_array_elements_text(r.vendors::jsonb) AS vendor(source)
        ), ordered_runs AS (
            SELECT search_term, source, occurred_at,
                   lag(occurred_at) OVER (
                       PARTITION BY search_term, source ORDER BY occurred_at
                   ) AS previous_at
            FROM expanded_runs
        ), cycle_runs AS (
            SELECT search_term, source, occurred_at,
                   sum(CASE WHEN previous_at IS NULL
                                 OR occurred_at - previous_at > INTERVAL '30 minutes'
                            THEN 1 ELSE 0 END) OVER (
                       PARTITION BY search_term, source ORDER BY occurred_at
                   ) AS cycle_id
            FROM ordered_runs
        ), scan_cycles AS (
            SELECT search_term, source, max(occurred_at) AS occurred_at
            FROM cycle_runs GROUP BY search_term, source, cycle_id
        ), ranked_runs AS (
            SELECT search_term, source, occurred_at,
                row_number() OVER (
                    PARTITION BY search_term, source ORDER BY occurred_at DESC
                ) AS run_rank
            FROM scan_cycles
        ), missed_cutoff AS (
            SELECT search_term, source, occurred_at
            FROM ranked_runs WHERE run_rank = :misses
        ), exact_sold AS (
            SELECT substring(source_url FROM '/itm/([0-9]{9,14})') AS ebay_item_id,
                   max(observed_at) AS sold_at
            FROM gem_radar_sold_observations
            WHERE source_url LIKE '%/itm/%'
            GROUP BY 1
        ), decisions AS (
            SELECT l.listing_id, l.observed_at,
                CASE
                    WHEN sold.sold_at > l.observed_at THEN 'sold'
                    WHEN cutoff.occurred_at > l.observed_at + INTERVAL '10 minutes' THEN 'archived'
                    WHEN l.observed_at < CURRENT_TIMESTAMP - INTERVAL '3 days' THEN 'archived'
                    ELSE 'active'
                END AS status,
                CASE
                    WHEN sold.sold_at > l.observed_at THEN 'exact_sold_item'
                    WHEN cutoff.occurred_at > l.observed_at + INTERVAL '10 minutes' THEN 'missed_scans'
                    WHEN l.observed_at < CURRENT_TIMESTAMP - INTERVAL '3 days' THEN 'unseen_3_days'
                    ELSE NULL
                END AS archive_reason
            FROM latest l
            LEFT JOIN missed_cutoff cutoff
              ON cutoff.search_term = l.search_query AND cutoff.source = l.source
            LEFT JOIN exact_sold sold ON sold.ebay_item_id = l.ebay_item_id
        )
        SELECT listing_id, status, archive_reason, observed_at,
               CASE WHEN status = 'active' THEN NULL ELSE CURRENT_TIMESTAMP END,
               CURRENT_TIMESTAMP
        FROM decisions
        WHERE true
        ON CONFLICT (listing_id) DO UPDATE SET
            status = EXCLUDED.status,
            archive_reason = EXCLUDED.archive_reason,
            last_seen_at = EXCLUDED.last_seen_at,
            archived_at = CASE
                WHEN EXCLUDED.status = 'active' THEN NULL
                WHEN gem_radar_listing_lifecycle.status = EXCLUDED.status
                    THEN gem_radar_listing_lifecycle.archived_at
                ELSE EXCLUDED.archived_at
            END,
            updated_at = CURRENT_TIMESTAMP
    """), {"misses": misses})
    rows = (await db.execute(text("""
        SELECT status, count(*) FROM gem_radar_listing_lifecycle GROUP BY status
    """))).all()
    return {status: int(count) for status, count in rows}
