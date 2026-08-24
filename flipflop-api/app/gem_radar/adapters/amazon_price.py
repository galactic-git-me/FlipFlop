"""Amazon UK New price adapter (PRD §11.6 — a separate, additional retail
benchmark, never substituted for used market value).

No Amazon Product Advertising API credentials exist anywhere in this
codebase (verified: `grep -i amazon app/config.py` had zero hits) and PA-API
access is gated behind an Amazon Associates account with 3 qualifying
referral sales in the trailing 180 days — a business requirement this
codebase can't satisfy on its own. LiveAmazonPriceAdapter sidesteps that
entirely by reusing app.scrapers.amazon_scraper, the Playwright-based scraper
already live and working for app.services.component_search's on-demand part
search — no application process, no credentials, works today.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

# LiveAmazonPriceAdapter launches a fresh, unpooled Chromium instance per
# call (see app.scrapers.amazon_scraper — no browser reuse). The general
# per-listing scoring concurrency (_SCORING_CONCURRENCY=25 in api/gem_radar.py)
# was sized for the old UnavailableAmazonPriceAdapter stub, which was
# instant. Left uncapped here, up to 25 listings hitting an Amazon cache
# miss at once means up to 25 simultaneous Chromium launches — heavy enough
# to slow the whole machine, not just this one adapter call. This semaphore
# throttles real browser launches independently of scoring concurrency.
_AMAZON_SCRAPE_CONCURRENCY = 3
_amazon_scrape_semaphore = asyncio.Semaphore(_AMAZON_SCRAPE_CONCURRENCY)


@dataclass
class AmazonPriceResult:
    available: bool
    price: float | None = None
    url: str | None = None
    observed_at: str | None = None
    unavailable_reason: str | None = None


class AmazonPriceAdapter(ABC):
    @abstractmethod
    async def fetch(self, query: str) -> AmazonPriceResult: ...


class UnavailableAmazonPriceAdapter(AmazonPriceAdapter):
    """Production adapter — PENDING. No Amazon Product Advertising API
    credentials are configured. Wire up a real integration here (subject to
    Amazon's API access approval and ToS) and swap this out in
    benchmarks.py.
    """

    async def fetch(self, query: str) -> AmazonPriceResult:
        return AmazonPriceResult(
            available=False,
            unavailable_reason="No Amazon pricing API credentials configured. See docs/ARCHITECTURE_GAP_ANALYSIS.md §4.",
        )


class LiveAmazonPriceAdapter(AmazonPriceAdapter):
    """Production adapter — real Amazon UK search via direct HTTP with realistic
    browser headers (app.scrapers.amazon_scraper_http.fetch_amazon_listings_http).
    Takes the first (most relevant, per Amazon's own search ranking) matching result
    rather than an average across several: this benchmark represents "a single
    retail listing, not a market sample" (see benchmarks.fetch_amazon_benchmark),
    the same semantics the previous stub adapter's caller already expected.
    """

    async def fetch(self, query: str) -> AmazonPriceResult:
        from app.scrapers.amazon_scraper_http import fetch_amazon_listings_http

        try:
            async with _amazon_scrape_semaphore:
                listings = await fetch_amazon_listings_http(search_terms=[query], min_price=1, max_price=20000)
        except Exception as exc:
            return AmazonPriceResult(available=False, unavailable_reason=f"Amazon scrape failed: {exc}")

        if not listings:
            return AmazonPriceResult(available=False, unavailable_reason="No matching Amazon listing found")

        top = listings[0]
        price = top.get("price")
        if not price or price <= 0:
            return AmazonPriceResult(available=False, unavailable_reason="Top Amazon result had no usable price")

        return AmazonPriceResult(
            available=True,
            price=float(price),
            url=top.get("url"),
            observed_at=datetime.now(timezone.utc).isoformat(),
        )


class FixtureAmazonPriceAdapter(AmazonPriceAdapter):
    """Deterministic in-memory fixture for tests."""

    def __init__(self, fixtures: dict[str, float]):
        self._fixtures = fixtures

    async def fetch(self, query: str) -> AmazonPriceResult:
        price = self._fixtures.get(query)
        if price is None:
            return AmazonPriceResult(available=False, unavailable_reason="No fixture price for this query")
        return AmazonPriceResult(available=True, price=price, url=None, observed_at=None)
