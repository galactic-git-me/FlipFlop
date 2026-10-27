"""Captured product media and the operator's explicit gallery selection."""
from sqlalchemy import text
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlparse

BUILD_MEDIA_ROOT = Path(__file__).resolve().parents[3] / "builds"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}


def own_build_media(build_id, photos, root=None):
    """Only public product media from an exactly linked build, never dispatch evidence."""
    root = root or BUILD_MEDIA_ROOT
    result = {"images": [], "videos": []}
    for item in photos or []:
        if isinstance(item, str):
            result["images"].append(item)
        elif isinstance(item, dict):
            kind = item.get("kind", "photo")
            if kind in {"photo", "video"} and item.get("url"):
                result["videos" if kind == "video" else "images"].append(item["url"])
    # Build-owned files may predate the database photo records.
    build_dir = root / str(build_id)
    if not build_dir.is_dir():
        build_dir = root / f"{build_id:03d}"
    media_dir = build_dir / "Media"
    if media_dir.is_dir() and media_dir.resolve().is_relative_to(root.resolve()):
        for path in sorted(media_dir.iterdir()):
            if not path.is_file() or not path.resolve().is_relative_to(media_dir.resolve()):
                continue
            kind = "images" if path.suffix.lower() in IMAGE_EXTENSIONS else "videos" if path.suffix.lower() in VIDEO_EXTENSIONS else None
            if kind:
                result[kind].append(f"/api/builds/{quote(path.relative_to(root).as_posix(), safe='/')}")
    return result


def _usable_media_url(url):
    if not isinstance(url, str) or not url.strip():
        return False
    if url.startswith("/api/builds/"):
        return True
    try:
        parsed = urlparse(url)
        path = unquote(parsed.path).casefold()
    except (TypeError, ValueError):
        return False
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return False
    if "._rc" in path or "<svg" in path or "/catalogsearch/result" in path:
        return False
    # A scraper once treated Google's inline base64 placeholder as a remote URL.
    host = parsed.hostname.casefold()
    if (host == "google.com" or host.endswith(".google.com")) and path.startswith("/ivborw0kggo"):
        return False
    return True


def media_urls(values):
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(url for url in values if _usable_media_url(url)))


def _colour_in_title(title):
    text = str(title or "").casefold()
    for colour in ("white", "black", "grey", "gray", "pink", "blue", "red"):
        if colour in text:
            return "grey" if colour == "gray" else colour
    return None


def _amazon_photo_id(url):
    match = re.search(r"/images/I/([^/.]+)", urlparse(str(url or "")).path, re.IGNORECASE)
    return match.group(1) if match else None


async def captured_media(db, category, cpk, asin=None):
    """Load media for a canonical product, optionally scoped to an exact colour ASIN."""
    rows = (await db.execute(text("""
        WITH products AS MATERIALIZED (
            SELECT DISTINCT ON (asin) asin, image_url, url, title, product_capture
            FROM amazon_bestseller_observations
            WHERE category = :category AND COALESCE(cpk, 'asin:' || asin) = :cpk
                AND (CAST(:asin AS text) IS NULL OR asin = CAST(:asin AS text))
            ORDER BY asin, captured_at DESC
        ), matched AS MATERIALIZED (
            SELECT DISTINCT ON (listing_id) listing_id, image_url, image_urls, video_urls, url, source, title
            FROM gem_radar_scored_listings
            WHERE cpk = :cpk AND category IN (:category,
                CASE :category WHEN 'storage' THEN 'ssd' WHEN 'cooler' THEN 'cooling' ELSE :category END)
            ORDER BY listing_id, scored_at DESC
        ), listing_ids AS (
            SELECT listing_id AS id FROM matched
            UNION SELECT asin FROM products
            UNION SELECT 'amazon-bestseller:' || asin FROM products
        )
        SELECT image_url,
            COALESCE(product_capture::jsonb -> 'product_image_urls', '[]'::jsonb) AS image_urls,
            '[]'::jsonb AS video_urls,
            url AS source_url, 'Amazon product' AS source, title AS product_title FROM products
        UNION ALL
        SELECT image_url, COALESCE(image_urls::jsonb, '[]'::jsonb),
            COALESCE(video_urls::jsonb, '[]'::jsonb), url, source, title FROM matched
        UNION ALL
        SELECT o.image_url, COALESCE(o.image_urls::jsonb, '[]'::jsonb),
            COALESCE(o.video_urls::jsonb, '[]'::jsonb), s.url, s.source, o.title
        FROM gem_radar_listing_observations o JOIN matched s ON s.listing_id = o.listing_id
        UNION ALL
        SELECT NULL, COALESCE(l.image_urls::jsonb, '[]'::jsonb)
                || COALESCE(l.raw_specs::jsonb -> 'playbook_product_capture' -> 'product_image_urls', '[]'::jsonb)
                || COALESCE(l.raw_specs::jsonb -> 'playbook_amazon_catalog_capture' -> 'product_image_urls', '[]'::jsonb),
            '[]'::jsonb,
            l.url, l.source_name, l.title
        FROM listings l WHERE l.external_id IN (SELECT id FROM listing_ids)
            OR l.url IN (SELECT url FROM products)
        UNION ALL
        SELECT NULL, COALESCE(f.generated_images_urls::jsonb, '[]'::jsonb),
            CASE WHEN f.generated_video_url IS NULL THEN '[]'::jsonb ELSE jsonb_build_array(f.generated_video_url) END,
            l.url, 'Our build media', l.title
        FROM flips f JOIN listings l ON l.id = f.listing_id
        WHERE l.external_id IN (SELECT id FROM listing_ids) OR l.url IN (SELECT url FROM products)
    """), {"category": category, "cpk": cpk, "asin": asin})).mappings().all()
    exact_colour = None
    excluded_photo_ids = set()
    if asin:
        title_row = (await db.execute(text("""
            SELECT title FROM gem_radar_scored_listings
            WHERE listing_id = :asin AND category = :category
            ORDER BY scored_at DESC LIMIT 1
        """), {"asin": asin, "category": category})).mappings().first()
        exact_colour = _colour_in_title(title_row["title"] if title_row else None)
        if exact_colour:
            product_row = (await db.execute(text("""
                SELECT title FROM amazon_bestseller_observations
                WHERE asin = :asin AND category = :category
                ORDER BY captured_at DESC LIMIT 1
            """), {"asin": asin, "category": category})).mappings().first()
            if product_row:
                sibling_products = (await db.execute(text("""
                    SELECT DISTINCT ON (asin) asin, image_url
                    FROM amazon_bestseller_observations
                    WHERE category = :category AND title = :title
                    ORDER BY asin, captured_at DESC
                """), {"category": category, "title": product_row["title"]})).mappings().all()
                sibling_asins = [row["asin"] for row in sibling_products]
                if sibling_asins:
                    sibling_scored = (await db.execute(text("""
                        SELECT DISTINCT ON (listing_id) listing_id, title
                        FROM gem_radar_scored_listings
                        WHERE category = :category AND listing_id = ANY(:asins)
                        ORDER BY listing_id, scored_at DESC
                    """), {"category": category, "asins": sibling_asins})).mappings().all()
                    sibling_colours = {row["listing_id"]: _colour_in_title(row["title"]) for row in sibling_scored}
                    excluded_photo_ids = {
                        photo_id for row in sibling_products
                        if row["asin"] != asin and sibling_colours.get(row["asin"])
                        and sibling_colours[row["asin"]] != exact_colour
                        if (photo_id := _amazon_photo_id(row["image_url"]))
                    }
    builds = (await db.execute(text("""
        SELECT b.id, b.name, b.photos, b.hero_photo_url,
            (SELECT s.title FROM gem_radar_scored_listings s
             WHERE s.listing_id = b.ebay_listing_id ORDER BY s.scored_at DESC LIMIT 1) AS product_title
        FROM manual_builds b
        WHERE b.ebay_listing_id IN (
            SELECT s.listing_id FROM gem_radar_scored_listings s
            WHERE s.cpk = :cpk AND s.category IN (CAST(:category AS text),
                CASE CAST(:category AS text) WHEN 'storage' THEN 'ssd' WHEN 'cooler' THEN 'cooling' ELSE CAST(:category AS text) END)
        )
    """), {"category": category, "cpk": cpk})).mappings().all()
    rows = list(rows)
    for build in builds:
        if exact_colour and _colour_in_title(build.get("product_title")) != exact_colour:
            continue
        media = own_build_media(build["id"], build["photos"])
        rows.append({"image_url": build["hero_photo_url"], "image_urls": media["images"],
                     "video_urls": media["videos"], "source_url": None,
                     "source": f"Our photos and clips · {build['name']}",
                     "product_title": build.get("product_title")})
    result = {"images": [], "videos": []}
    for row in rows:
        if exact_colour and row["source"] != "Amazon product" and _colour_in_title(row.get("product_title")) != exact_colour:
            continue
        for kind, urls in (("images", media_urls([row["image_url"], *(row["image_urls"] or [])])),
                           ("videos", media_urls(row["video_urls"] or []))):
            for url in urls:
                if kind == "images" and _amazon_photo_id(url) in excluded_photo_ids:
                    continue
                if not any(item["url"] == url for item in result[kind]):
                    result[kind].append({"url": url, "source": row["source"], "href": row["source_url"]})
    return result


def validate_selection(selection, captured):
    for kind in ("images", "videos"):
        selected = selection[kind]
        if len(selected) != len(set(selected)):
            raise ValueError("Choose each photo or video only once")
        allowed = {item["url"] for item in captured[kind]}
        if any(url not in allowed for url in selected):
            raise ValueError("Only captured media for this product can be selected; refresh the gallery")
    if not selection["images"]:
        raise ValueError("Choose at least one photo for the curated catalogue")


def selected_gallery(selection, kind):
    """Materialize the saved allowlist; never add newly captured photos to it."""
    return [{"url": url, "title": "Selected product photo" if kind == "images" else "Selected product video",
             "source": "Curated catalogue selection", "href": None}
            for url in media_urls(selection.get(kind, []))]
