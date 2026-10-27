"""Commercial capture is immutable even when a search sighting is touched."""
from datetime import timezone
import re


AVAILABILITY_FALLBACK = 'owner-approved: current scraped listing assumed available unless explicitly unavailable'


def search_listing_availability(status=None, evidence=None, *, listing_type='buy_it_now', sold_confirmed=False, active=True):
    """Owner policy for current listings; explicit sold/out-of-stock always wins."""
    negative = bool(re.search(r'\b(?:sold\s*out|out\s*of\s*stock|unavailable|listing\s*(?:has\s*)?ended|item\s*(?:has\s*)?sold)\b', str(evidence or ''), re.I))
    if status == 'unavailable' or negative or sold_confirmed:
        return 'unavailable', evidence or 'explicitly unavailable or sold', False
    if not active or listing_type != 'buy_it_now':
        return status or 'unknown', evidence, False
    if status == 'available':
        return status, evidence or AVAILABILITY_FALLBACK, not bool(evidence)
    return 'available', AVAILABILITY_FALLBACK, True


def commercial_capture(listing):
    captured = listing.extracted_at
    # Legacy naive captures cannot establish fresh automated availability.
    aware = captured.tzinfo is not None
    status, evidence, assumed = search_listing_availability(
        listing.stock_status, listing.stock_evidence,
        listing_type=listing.listing_type, sold_confirmed=getattr(listing,'sold_confirmed',False))
    return {
        'observed_at': captured.astimezone(timezone.utc).isoformat() if aware else None,
        'url': listing.url,
        'item_gbp': str(listing.item_price),
        'delivery_gbp': str(listing.postage_price),
        'source_currency': listing.source_currency,
        'source_item_price': listing.source_item_price,
        'exchange_rate': listing.exchange_rate,
        'exchange_rate_date': listing.exchange_rate_date,
        'exchange_rate_source': listing.exchange_rate_source,
        'stock_status': status,
        'stock_evidence': evidence,
        'availability_assumed': assumed,
    }
