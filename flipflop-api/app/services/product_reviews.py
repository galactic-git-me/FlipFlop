"""CPK-level product review aggregation."""

from collections.abc import Iterable


def review_vendor(source: str | None) -> str:
    """Collapse source labels into marketplace vendors for deduplication."""
    value = (source or "unknown").strip().lower()
    if "amazon" in value:
        return "amazon"
    if "ebay" in value:
        return "ebay"
    return value or "unknown"


def aggregate_cpk_reviews(
    observations: Iterable[tuple[str, str | None, float | None, int | None]],
) -> dict[str, tuple[float | None, int | None]]:
    """Combine one strongest review observation per vendor for each CPK.

    A marketplace can produce several scored rows for the same CPK. The
    highest review count is retained for that vendor, then vendor counts are
    added and ratings are weighted by those counts.
    """
    by_vendor: dict[tuple[str, str], tuple[float | None, int | None]] = {}
    for cpk, source, rating, count in observations:
        if not cpk or (rating is None and count is None):
            continue
        if count is not None and count < 0:
            continue
        key = (cpk, review_vendor(source))
        current = by_vendor.get(key)
        if current is None or (count or 0) > (current[1] or 0):
            by_vendor[key] = (rating, count)

    combined: dict[str, tuple[float | None, int | None]] = {}
    for (cpk, _vendor), (rating, count) in by_vendor.items():
        if count is None:
            continue
        old_rating, old_count = combined.get(cpk, (None, 0))
        total_count = (old_count or 0) + count
        if total_count == 0:
            combined[cpk] = (rating if old_rating is None else old_rating, 0)
        elif rating is not None and old_rating is not None and old_count:
            combined[cpk] = (
                ((old_rating * old_count) + (rating * count)) / total_count,
                total_count,
            )
        elif rating is not None:
            combined[cpk] = (rating, total_count)
        else:
            combined[cpk] = (old_rating, total_count)
    return combined
