"""Marketplace inference from listing URL.

ExtractedListing has no explicit marketplace/source field — the extension
scrapes eBay, Vinted, Overclockers, and Temu in one sweep per search term and
submits all four's results in a single combined `listings` array with no
origin tag. Rather than requiring an extension-side schema change, this
infers the marketplace from the listing's own URL domain, which is already
present on every ExtractedListing.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# Amazon ASINs (B0 + 8 alphanumeric chars) are a recognisable shape even
# when `source` was never recorded (e.g. pre-fix historical rows written
# before Amazon was added to _DOMAIN_TO_MARKETPLACE below) — used only as a
# last-resort signal in fallback_listing_url, never to override a real,
# already-known source.
_ASIN_PATTERN = re.compile(r"^B0[A-Z0-9]{8}$")

_DOMAIN_TO_MARKETPLACE: dict[str, str] = {
    "ebay.co.uk": "ebay",
    "ebay.com": "ebay",
    "vinted.co.uk": "vinted",
    "vinted.com": "vinted",
    "overclockers.co.uk": "overclockers",
    "temu.com": "temu",
    # Amazon was missing entirely despite being one of the 5 marketplaces
    # the extension actually scrapes — every Amazon-sourced observation
    # silently got source=None instead, which is exactly why "active from
    # source=None" turned out to be the single largest group when this got
    # investigated (most of that bucket was misclassified Amazon listings,
    # not genuinely unknown ones).
    "amazon.co.uk": "amazon",
    "amazon.com": "amazon",
    "uk.webuy.com": "cex",
    "webuy.com": "cex",
    "aliexpress.com": "aliexpress",
    # Scanned by the extension (scan-orchestrator.ts's SLOW_SPA_MARKETPLACES)
    # but missing here entirely -- every Scan.co.uk observation fell through
    # to source=None and got misbucketed as "unknown" on the dashboard.
    "scan.co.uk": "scan",
    "awd-it.co.uk": "awd_it",
    "computerorbit.com": "computer_orbit",
    "bargainhardware.co.uk": "bargain_hardware",
}

# Marketplaces excluded from contributing to price benchmarks. Temu: "new"
# listings carry meaningful counterfeit/drop-ship risk for PC components —
# pooling them unfiltered into a "new" price benchmark alongside genuine
# retailer/marketplace stock would let suspiciously-cheap knockoff pricing
# drag the whole benchmark down without the scoring model ever knowing why.
# Vinted: only eBay, Amazon, and Overclockers are treated as reputable
# pricing sources — Vinted is peer-to-peer secondhand with no equivalent
# verification/buyer-protection signal, so it's scored as a candidate
# listing like any other but never allowed to set the price bar. Excluded
# from price-index contribution entirely rather than down-weighted, since
# there's no reliable signal here to weight by.
UNTRUSTED_FOR_PRICE_BENCHMARKS = frozenset({"temu", "vinted"})


def infer_marketplace(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return None
    host = host.lower().removeprefix("www.")
    for domain, marketplace in _DOMAIN_TO_MARKETPLACE.items():
        if host == domain or host.endswith(f".{domain}"):
            return marketplace
    return None


# Per-marketplace URL template, used only as a fallback for scored rows
# written before GemRadarScoredListing.url existed (real scraped URLs are
# stored directly now — see the model). Every "view listing" link in the
# app used to be a hardcoded f"https://www.ebay.co.uk/itm/{listing_id}/"
# regardless of source, silently producing a wrong/dead link for every
# non-eBay listing; this is at least marketplace-correct for the fields we
# do know (listing_id, source), though not guaranteed to resolve to the
# exact original listing the way a stored real URL does.
_FALLBACK_URL_TEMPLATES: dict[str, str] = {
    "ebay": "https://www.ebay.co.uk/itm/{listing_id}",
    "vinted": "https://www.vinted.co.uk/items/{listing_id}",
    "amazon": "https://www.amazon.co.uk/dp/{listing_id}",
}

# Marketplaces with no ID-based product URL we can reconstruct (their
# listing_id isn't a URL path segment we know the shape of) -- a listing
# title, when available, at least lands on that marketplace's own search
# results for the right product, instead of silently falling through to
# the eBay template above and opening a wrong eBay page for a completely
# different item (the exact bug this module's docstring already describes,
# just for the marketplaces the ID-template dict never covered).
_FALLBACK_SEARCH_TEMPLATES: dict[str, str] = {
    "overclockers": "https://www.overclockers.co.uk/search?sSearch={query}",
    "cex": "https://uk.webuy.com/search?stext={query}",
    "temu": "https://www.temu.com/search_result.html?search_key={query}",
    "aliexpress": "https://www.aliexpress.com/wholesale?SearchText={query}",
    "awd_it": "https://www.awd-it.co.uk/catalogsearch/result/?q={query}",
    "computer_orbit": "https://computerorbit.com/search?q={query}&type=product",
    "bargain_hardware": "https://www.bargainhardware.co.uk/catalogsearch/result/?q={query}",
}


def fallback_listing_url(listing_id: str, source: str | None, title: str | None = None) -> str:
    if source is None and _ASIN_PATTERN.match(listing_id):
        source = "amazon"

    id_template = _FALLBACK_URL_TEMPLATES.get(source or "")
    if id_template:
        return id_template.format(listing_id=listing_id)

    search_template = _FALLBACK_SEARCH_TEMPLATES.get(source or "")
    if search_template and title:
        from urllib.parse import quote_plus

        return search_template.format(query=quote_plus(title))

    # Last resort only: no known template for this source at all (or a
    # search template exists but no title was passed in) -- eBay's
    # ID-shaped template is wrong for a non-eBay listing_id, but it's the
    # same degraded behavior this function has always had for truly
    # unknown sources, not a regression.
    return _FALLBACK_URL_TEMPLATES["ebay"].format(listing_id=listing_id)


def usable_listing_url(
    url: str | None,
    listing_id: str,
    source: str | None,
    title: str | None = None,
) -> str:
    """Return an item-level URL, replacing retailer homepages with a fallback.

    Older extension observations sometimes recorded the page's canonical
    retailer homepage instead of the product anchor.  A non-empty homepage is
    not useful as a "view listing" target, so treat it the same as a missing
    URL.  This is deliberately narrow: paths, query strings, and fragments are
    preserved because they can identify a product or a useful search page.
    """
    if url:
        try:
            parsed = urlparse(url)
            is_homepage = parsed.path.rstrip("/") == "" and not parsed.query and not parsed.fragment
        except ValueError:
            is_homepage = False
        if not is_homepage:
            return url

    return fallback_listing_url(listing_id, source, title)
