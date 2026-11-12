"""Commercial capture is immutable even when a search sighting is touched."""
from datetime import timezone
import re
from urllib.parse import urlsplit


def search_listing_availability(status=None, evidence=None, *, listing_type='buy_it_now', sold_confirmed=False, active=True):
    """Use only explicit, current stock evidence; unknown stock remains unknown."""
    negative = bool(re.search(r'\b(?:sold\s*out|out\s*of\s*stock|unavailable|listing\s*(?:has\s*)?ended|item\s*(?:has\s*)?sold)\b', str(evidence or ''), re.I))
    if status == 'unavailable' or negative or sold_confirmed:
        return 'unavailable', evidence or 'explicitly unavailable or sold', False
    if status == 'available' and not evidence:
        return 'unknown', None, False
    if not active or listing_type != 'buy_it_now':
        return status or 'unknown', evidence, False
    if status == 'available' and evidence:
        return status, evidence, False
    return 'unknown', evidence, False


def commercial_capture(listing):
    captured = listing.extracted_at
    # Legacy naive captures cannot establish fresh automated availability.
    aware = captured is not None and captured.tzinfo is not None
    status, evidence, assumed = search_listing_availability(
        listing.stock_status if aware else 'unknown', listing.stock_evidence if aware else None,
        listing_type=getattr(listing, 'listing_type', 'unknown'),
        sold_confirmed=getattr(listing,'sold_confirmed',False))
    source_product = getattr(listing, 'supplier_product_evidence', None)
    if source_product is not None and hasattr(source_product, 'model_dump'):
        source_product = source_product.model_dump(mode='json')
    if isinstance(source_product, dict):
        page = urlsplit(str(source_product.get('page_url') or ''))
        listing_url = urlsplit(str(listing.url or ''))
        exact_page = (page.scheme == listing_url.scheme == 'https'
            and page.hostname in {'gamers-outlet.net', 'www.gamers-outlet.net'}
            and (page.hostname or '').casefold() == (listing_url.hostname or '').casefold()
            and page.path.rstrip('/').casefold() == listing_url.path.rstrip('/').casefold())
        try:
            product_capture_at = datetime.fromisoformat(str(source_product.get('captured_at') or '').replace('Z', '+00:00'))
            capture_matches_listing = (captured is not None and product_capture_at.tzinfo is not None
                and captured.tzinfo is not None
                and abs((product_capture_at - captured).total_seconds()) <= 60)
        except (TypeError, ValueError):
            capture_matches_listing = False
        if not exact_page or not capture_matches_listing:
            source_product = None
    else:
        source_product = None
    return {
        'observed_at': captured.astimezone(timezone.utc).isoformat() if aware else None,
        'url': listing.url,
        'item_gbp': str(listing.item_price),
        'delivery_gbp': str(listing.postage_price),
        'source_currency': getattr(listing, 'source_currency', None),
        'source_item_price': getattr(listing, 'source_item_price', None),
        'exchange_rate': getattr(listing, 'exchange_rate', None),
        'exchange_rate_date': getattr(listing, 'exchange_rate_date', None),
        'exchange_rate_source': getattr(listing, 'exchange_rate_source', None),
        'stock_status': status,
        'stock_evidence': evidence,
        'availability_assumed': assumed,
        'supplier_product_evidence': source_product,
    }
