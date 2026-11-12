"""Apply the owner-enabled automatic approval to captured bestseller images."""
from sqlalchemy import text


async def auto_approve_captured_bestseller_images(db) -> int:
    """Approve usable, latest Amazon listing images without overriding rejections."""
    result = await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (category, asin)
                   category, COALESCE(cpk, 'asin:' || asin) AS cpk, image_url
            FROM amazon_bestseller_observations
            ORDER BY category, asin, captured_at DESC, id DESC
        ), eligible AS (
            SELECT category, cpk
            FROM latest
            WHERE image_url ~* '^https?://'
              AND image_url NOT LIKE '%._RC'
        )
        INSERT INTO curated_bestseller_reviews (category, cpk, status, reviewed_at, selected_media)
        SELECT category, cpk, 'approved', now(), '{"images":[],"videos":[]}'::jsonb
        FROM eligible
        ON CONFLICT (category, cpk) DO UPDATE
        SET status = 'approved', reviewed_at = now(),
            selected_media = COALESCE(curated_bestseller_reviews.selected_media, EXCLUDED.selected_media)
        WHERE curated_bestseller_reviews.status <> 'rejected'
        RETURNING category, cpk
    """))
    return len(result.fetchall())
