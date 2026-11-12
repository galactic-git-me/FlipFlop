"""
Live resale price scraper.

CORE PRINCIPLE: Resale price is determined by what similar PCs ACTUALLY sell for
in the market — NOT the sum of their components.  Market always overrides theory.

Fallback chain (in order):
  1. Whole-system eBay comps — "gaming PC i5-9600K RTX 3060" sold listings.
     The gold standard: real buyers, real prices.  Requires ≥ 2 comps.
  2. Buy-price formula       — anchors to the listing's own market price:
     (listing_price + upgrade_value_adds + £100 case premium) × 1.20.
     The seller already priced to market, so their ask is a market signal.
  3. Static CPU-table        — last resort when no buy_price supplied.

❌ Component pricing (sum-of-parts × multiplier) is NOT used as a resale
   estimate.  It is available separately as a sanity-check only.

Key filtering to avoid low auction starting bids:
- No LH_BIN=1 (breaks sold-listings on eBay UK, returns 0 results).
- Auctions filtered in Python by bid-count element.
- Price ranges ("£x to £y") skipped.
"""

import re
from dataclasses import dataclass, field
import structlog

from app.services.estimator import (
    estimate_resale as _static_estimate,
    BUDGET_CASE_RESALE_ADD,
    BUDGET_GPU_RESALE_ADD,
    BUDGET_SSD_RESALE_ADD,
)
from app.services.ebay_browse import search_active_listings

# When no eBay comps are found we fall back to a price derived from what the
# seller is already asking (the market has priced the PC).  We then stack on
# what each upgrade adds to resale value, a generous themed-case premium, and
# a 20 % flip surcharge — reflecting what buyers pay for a ready-to-go,
# themed build vs. sourcing and assembling it themselves.
_FALLBACK_CASE_PREMIUM = 100   # £100 — cases can cost up to £80, themed premium is real
_FALLBACK_FLIP_SURCHARGE = 1.20  # 20 % above sum-of-parts for a finished, themed build

log = structlog.get_logger(__name__)

# Per-run cache: spec fingerprint → ResaleRange
_cache: dict[str, "ResaleRange"] = {}
@dataclass
class ResaleRange:
    low: float    # 25th-percentile sold price
    median: float # 50th-percentile (stored as estimated_resale)
    high: float   # 75th-percentile
    count: int    # real comps found (0 = static fallback)
    query: str = ""


# ── Audit / debug data structures ────────────────────────────────────────────

@dataclass
class SoldComp:
    """One sold eBay listing captured during comp scraping."""
    title: str
    price: float
    url: str = ""
    excluded: bool = False
    exclusion_reason: str = ""   # e.g. "auction", "price range", "price out of range"


@dataclass
class ResaleAudit:
    """
    Full transparent trace of a resale estimate — every input, every filter,
    every calculation step.  Built by get_resale_audit().
    """
    # ── Step 1: Source data ───────────────────────────────────────────────────
    query: str
    ebay_url: str = ""                      # sold capture is extension-owned
    all_comps: list[SoldComp] = field(default_factory=list)   # ALL items seen
    included_comps: list[SoldComp] = field(default_factory=list)  # passed filters
    excluded_comps: list[SoldComp] = field(default_factory=list)  # failed filters

    # ── Step 2: Raw price set ─────────────────────────────────────────────────
    prices: list[float] = field(default_factory=list)
    price_min: float = 0.0
    price_max: float = 0.0
    price_median: float = 0.0
    price_avg: float = 0.0

    # ── Step 3: Exact calculation ─────────────────────────────────────────────
    tier_used: str = ""          # "live_comps" / "buy_price_formula" / "static_table"
    case_premium_added: float = 0.0
    resale_low: float = 0.0
    resale_median: float = 0.0
    resale_high: float = 0.0
    calculation_steps: list[str] = field(default_factory=list)

    # ── Step 5: Sanity check ──────────────────────────────────────────────────
    buy_price: float | None = None
    sanity_verdict: str = ""     # "YES" / "NO" / "MARGINAL"
    sanity_explanation: str = ""


def clear_cache() -> None:
    _cache.clear()


def _spec_key(cpu: str | None, ram_gb: int | None, gpu: str | None, storage_gb: int | None) -> str:
    def norm(s: str | None) -> str:
        return re.sub(r"\s+", " ", (s or "").lower().strip())[:40]
    return f"{norm(cpu)}|{ram_gb or 0}|{norm(gpu)}|{storage_gb or 0}"


def _build_query(cpu: str | None, gpu: str | None) -> str:
    """
    Deliberately short query — too many terms kill result count on completed listings.
    CPU generation + GPU model is enough to find comparable sales.

    When the listing has no GPU we will be adding one during the flip, so we
    include a budget GPU ("rx 580") in the query.  This ensures the comps
    reflect the FINISHED product we will sell rather than a bare, GPU-less PC.
    """
    parts = ["gaming PC"]

    if cpu:
        cpu_l = cpu.lower()
        m = re.search(
            r"(i[3579]-\d{4,5}[a-z]*|ryzen\s+[3579]\s+\d{4}[a-z]*|xeon\s+\w[\w-]+)",
            cpu_l,
        )
        if m:
            parts.append(m.group(0).strip())
        else:
            short = re.sub(r"intel\s+core\s*|amd\s+", "", cpu_l).strip()[:20]
            if short:
                parts.append(short)

    if gpu:
        gpu_l = gpu.lower()
        m = re.search(r"(gtx|rtx|rx)\s*\d{3,4}(\s*(ti|xt|super))?", gpu_l)
        if m:
            parts.append(m.group(0).strip())
    else:
        # No GPU in listing — we'll add an RTX 3060-class card when we flip it.
        # Use it in the query so comps represent the complete finished product.
        parts.append("rtx 3060")

    return " ".join(parts)


async def _fetch_active_prices(query: str) -> list[float]:
    """
    Scrape current live BIN listings for the same spec — what sellers are
    asking RIGHT NOW.  Used as Tier 2 when sold comps are unavailable.
    Results are discounted by 0.92 at the call site so we price below competition.

    Rate limited to max 2 concurrent requests to avoid eBay throttling.
    """
    # Current listings use the authenticated Browse API.  This avoids the
    # HTML endpoint that is generating the 403 storm in the queue.
    try:
        listings = await search_active_listings(
            query,
            condition_filter="USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE",
            limit=50,
            min_price=80.0,
        )
        prices = [float(item["price"]) for item in listings if 80.0 < float(item["price"]) < 1400.0]
        log.debug("resale_scraper.ebay_active_api", query=query, found=len(prices))
        return prices
    except Exception as exc:
        log.warning("resale_scraper.ebay_active_api_error", query=query, error=str(exc))
        return []

async def get_resale_range(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    storage_type: str | None,
    gpu: str | None,
    buy_price: float | None = None,
) -> ResaleRange:
    """
    Main entry point. Returns a ResaleRange from real eBay data when possible.

    Fallback priority:
      1. eBay sold/completed BIN comps  — what buyers actually paid
      2. eBay active BIN listings × 0.92 — current ask prices, discounted to
         undercut competition and sell quickly
      3. Buy-price formula              — floor when eBay is unreachable
      4. Static CPU-table              — last resort, no buy_price available

    Tier 1 and Tier 2 results are cached by spec key for the swarm run.
    Tier 3 is NOT cached — it is listing-specific.
    """
    key = _spec_key(cpu, ram_gb, gpu, storage_gb)
    if key in _cache:
        return _cache[key]

    query = _build_query(cpu, gpu)
    case_add = BUDGET_CASE_RESALE_ADD

    # ── Tier 1: eBay active listings × 0.92 ──────────────────────────────────
    active = await _fetch_active_prices(query)
    if len(active) >= 2:
        active.sort()
        n = len(active)
        # Discount to price below current competition; add case uplift
        low    = round(active[n // 4]                * 0.92 + case_add, 2)
        median = round(active[n // 2]                * 0.92 + case_add, 2)
        high   = round(active[min(n - 1, (n*3)//4)] * 0.92 + case_add, 2)
        result = ResaleRange(low=low, median=median, high=high, count=n, query=query)
        log.info("resale_scraper.tier2_active_listings", query=query, count=n,
                 low=low, median=median, high=high)
        _cache[key] = result
        return result

    # ── Tier 3: buy-price formula ─────────────────────────────────────────────
    if buy_price is not None:
        upgrade_resale = 0.0
        if not gpu:
            upgrade_resale += BUDGET_GPU_RESALE_ADD
        if not storage_gb:
            upgrade_resale += BUDGET_SSD_RESALE_ADD

        subtotal = buy_price + upgrade_resale + _FALLBACK_CASE_PREMIUM
        median   = round(subtotal * _FALLBACK_FLIP_SURCHARGE, 2)
        low      = round(median * 0.88, 2)
        high     = round(median * 1.12, 2)
        result   = ResaleRange(low=low, median=median, high=high,
                               count=0, query=query)
        log.debug("resale_scraper.tier3_buy_price_formula",
                  query=query, buy_price=buy_price, median=median)
        return result  # not cached — listing-specific

    # ── Tier 4: static CPU-table ──────────────────────────────────────────────
    static = _static_estimate(cpu, ram_gb, ram_type, storage_gb, storage_type, gpu)
    result = ResaleRange(
        low=round(static * 0.85, 2),
        median=static,
        high=round(static * 1.15, 2),
        count=0,
        query=query,
    )
    log.debug("resale_scraper.tier4_static_table", query=query, static=static)
    _cache[key] = result
    return result


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0


# ── Auction buy-price estimation ──────────────────────────────────────────────
#
# Problem:
#   Auction listings show the CURRENT BID — almost always far below where the
#   auction will close.  Using it as the "buy price" wildly overestimates profit.
#   BIN prices go the other way — too high (sellers anchor high for BIN).
#
# Solution:
#   Fetch COMPLETED eBay AUCTION prices for similar hardware.  These are the
#   actual hammer prices that real buyers paid at auction for comparable raw PCs.
#   Take the median: that's the realistic expected cost-of-entry.
#
# Fallback (< 2 comps found):
#   UK PC auctions typically close 25–40% above the current bid.
#   We use ×1.35 as a conservative midpoint.

_auction_price_cache: dict[str, float] = {}


def _build_auction_comp_query(cpu: str | None, gpu: str | None) -> str:
    """
    Short query for finding comparable completed auction prices.
    We deliberately DON'T include a GPU here — we're pricing the raw bare-bones
    PC that we'll buy at auction, NOT the finished flipped product.
    """
    parts: list[str] = []
    if cpu:
        m = re.search(
            r"(i[3579]-\d{4,5}[a-z]*|ryzen\s+[3579]\s+\d{4}[a-z]*|xeon\s+\w[\w-]+)",
            cpu.lower(),
        )
        if m:
            parts.append(m.group(0).strip())
        else:
            short = re.sub(r"intel\s+core\s*|amd\s+", "", cpu.lower()).strip()[:20]
            if short:
                parts.append(short)
    # Add either "gaming pc" or "pc tower" depending on whether it has a GPU
    parts.append("gaming pc" if gpu else "pc tower")
    return " ".join(parts) if parts else "pc tower"


async def get_expected_auction_price(
    cpu: str | None,
    gpu: str | None,
    current_bid: float,
) -> float:
    """Estimate from current bid; backend eBay sold requests are disabled."""
    return round(current_bid * 1.35, 2)


def clear_auction_cache() -> None:
    _auction_price_cache.clear()


# ── Audit / debug functions ───────────────────────────────────────────────────

async def get_resale_audit(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    storage_type: str | None,
    gpu: str | None,
    buy_price: float | None = None,
) -> ResaleAudit:
    """
    Full transparent audit of a resale estimate.

    Runs the same pipeline as get_resale_range() but captures every comp seen,
    every exclusion reason, every calculation step — so the valuation is
    fully auditable.  NOT cached (always live).
    """
    from app.services.estimator import (
        estimate_resale as _static_est,
        BUDGET_CASE_RESALE_ADD as CASE_ADD,
        BUDGET_GPU_RESALE_ADD  as GPU_ADD,
        BUDGET_SSD_RESALE_ADD  as SSD_ADD,
        PLATFORM_FEE,
    )

    query  = _build_query(cpu, gpu)
    audit  = ResaleAudit(query=query, buy_price=buy_price)

    # Sold evidence is captured in FlipFlopXtension; this backend audit does no sold-page requests.
    prices: list[float] = []

    # ── Step 3: Exact calculation ─────────────────────────────────────────────
    if len(prices) >= 2:
        # Tier 1: live comps
        prices_sorted = sorted(prices)
        n = len(prices_sorted)
        raw_low    = prices_sorted[n // 4]
        raw_median = prices_sorted[n // 2]
        raw_high   = prices_sorted[min(n - 1, (n * 3) // 4)]

        audit.tier_used          = "live_comps"
        audit.case_premium_added = CASE_ADD

        audit.resale_low    = round(raw_low    + CASE_ADD, 2)
        audit.resale_median = round(raw_median + CASE_ADD, 2)
        audit.resale_high   = round(raw_high   + CASE_ADD, 2)

        audit.calculation_steps = [
            f"Found {n} comparable sold listings on eBay UK.",
            f"Prices (sorted): {[f'£{p:.0f}' for p in prices_sorted]}",
            f"25th-pct (low):    £{raw_low:.0f}",
            f"50th-pct (median): £{raw_median:.0f}",
            f"75th-pct (high):   £{raw_high:.0f}",
            f"Added themed-case premium: +£{CASE_ADD:.0f} (2 × case cost, per flip spec)",
            f"Final resale range: £{audit.resale_low:.0f} / £{audit.resale_median:.0f} / £{audit.resale_high:.0f}",
            "NOTE: eBay comps are generic/unthemed builds. Case premium adjusts for "
            "our finished, themed product which commands a higher price.",
        ]

    elif buy_price is not None:
        # Tier 2: buy-price formula
        upgrade_resale = 0.0
        upgrade_detail = []
        if not gpu:
            upgrade_resale += GPU_ADD
            upgrade_detail.append(f"GPU value add: +£{GPU_ADD:.0f} (RTX 3060 upgrade)")
        if not storage_gb:
            upgrade_resale += SSD_ADD
            upgrade_detail.append(f"SSD value add: +£{SSD_ADD:.0f} (1 TB NVMe upgrade)")

        subtotal = buy_price + upgrade_resale + _FALLBACK_CASE_PREMIUM
        median   = round(subtotal * _FALLBACK_FLIP_SURCHARGE, 2)

        audit.tier_used          = "buy_price_formula"
        audit.case_premium_added = _FALLBACK_CASE_PREMIUM
        audit.resale_low         = round(median * 0.88, 2)
        audit.resale_median      = median
        audit.resale_high        = round(median * 1.12, 2)

        steps = [
            f"⚠️  No eBay comps found (< 2 sold listings matched query: '{query}').",
            f"Falling back to buy-price formula (seller has priced to market).",
            f"Buy price:            £{buy_price:.0f}",
        ] + upgrade_detail + [
            f"Case premium:         +£{_FALLBACK_CASE_PREMIUM:.0f}",
            f"Subtotal:             £{subtotal:.0f}",
            f"Flip surcharge × {_FALLBACK_FLIP_SURCHARGE}: £{median:.0f}  (buyer pays for tested, ready-to-go build)",
            f"Range: £{audit.resale_low:.0f} (−12%) / £{median:.0f} / £{audit.resale_high:.0f} (+12%)",
        ]
        audit.calculation_steps = steps

    else:
        # Tier 3: static table
        static = _static_est(cpu, ram_gb, ram_type, storage_gb, storage_type, gpu)
        audit.tier_used     = "static_table"
        audit.resale_low    = round(static * 0.85, 2)
        audit.resale_median = static
        audit.resale_high   = round(static * 1.15, 2)

        audit.calculation_steps = [
            f"⚠️  No eBay comps found and no buy_price supplied.",
            f"Using static CPU/GPU lookup table (last resort).",
            f"Static estimate: £{static:.0f}",
            f"Range: £{audit.resale_low:.0f} (−15%) / £{static:.0f} / £{audit.resale_high:.0f} (+15%)",
        ]

    # ── Step 5: Sanity check ──────────────────────────────────────────────────
    if buy_price is not None:
        gap = audit.resale_median - buy_price
        # After upgrade costs (rough: case + GPU if needed)
        rough_upgrade = 70 + (185 if not gpu else 0) + (65 if not storage_gb else 0) + 65
        rough_fees    = audit.resale_median * PLATFORM_FEE
        rough_profit  = audit.resale_median - buy_price - rough_upgrade - rough_fees

        if rough_profit >= 50:
            audit.sanity_verdict = "YES"
            audit.sanity_explanation = (
                f"Median resale £{audit.resale_median:.0f} vs buy price £{buy_price:.0f} "
                f"leaves ~£{rough_profit:.0f} after upgrade costs and fees. "
                f"This is a viable flip."
            )
        elif rough_profit >= 0:
            audit.sanity_verdict = "MARGINAL"
            audit.sanity_explanation = (
                f"Median resale £{audit.resale_median:.0f} vs buy price £{buy_price:.0f}. "
                f"After costs, rough profit is only ~£{rough_profit:.0f}. "
                f"Tight margin — condition risk or slow sale could erase profit."
            )
        else:
            audit.sanity_verdict = "NO"
            audit.sanity_explanation = (
                f"Median resale £{audit.resale_median:.0f} vs buy price £{buy_price:.0f}. "
                f"After upgrade costs (~£{rough_upgrade:.0f}) and fees (~£{rough_fees:.0f}), "
                f"this produces a LOSS of ~£{abs(rough_profit):.0f}. "
                f"{'The buy price exceeds what comparable FINISHED PCs sell for.' if gap < 0 else 'Upgrade costs eat the margin.'}"
            )

    return audit
