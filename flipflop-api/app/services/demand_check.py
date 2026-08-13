"""
Demand-check service — Algorithm Playbook rows 10, 33.

Fires automatically the moment a Flip is created: pulls sold-vs-active
counts for the build's spec over the last 90 days so demand and margin can
be judged side by side before parts are committed. Row 33 ("avoid precise
sell-through-rate formulas") is deliberately honoured by keeping the output
a simple sold-vs-active ratio — no compound formula on top of it.

Active-listing counts come from the eBay Browse API (already wired via
app.services.ebay_browse). Sold-listing counts require eBay's Marketplace
Insights API (`buy/marketplace_insights/v1_beta/item_sales/search`), which
is a restricted-access scope eBay grants on a per-application basis — many
developer accounts are never approved for it. This service calls it and
degrades gracefully (sold_count_90d = None, a note explaining why) rather
than failing the whole demand check when that scope isn't available, since
FlipFlop's current app credentials have not been confirmed to have it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog

from app.api.ebay_compliance import _get_app_token, _ebay_api_root
from app.services.ebay_browse import get_component_prices

log = structlog.get_logger(__name__)

_MARKETPLACE_ID = "EBAY_GB"


@dataclass
class DemandSignal:
    query: str
    active_count: Optional[int]
    sold_count_90d: Optional[int]
    checked_at: datetime
    sold_data_available: bool
    note: Optional[str] = None

    @property
    def ratio_ok(self) -> Optional[bool]:
        """True if there's enough sold history relative to active competition."""
        if self.sold_count_90d is None or self.active_count is None:
            return None
        if self.active_count == 0:
            return self.sold_count_90d > 0
        return (self.sold_count_90d / self.active_count) >= 0.15


def build_query(cpu: Optional[str], gpu: Optional[str]) -> str:
    """Builds a search query from a build's spec, mirroring how the title generator sources terms."""
    parts = [p for p in [cpu, gpu, "gaming pc"] if p]
    return " ".join(parts).strip() or "gaming pc"


async def _sold_count_90d(token: str, query: str) -> tuple[Optional[int], Optional[str]]:
    since = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    root = _ebay_api_root()
    url = f"{root}/buy/marketplace_insights/v1_beta/item_sales/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": _MARKETPLACE_ID,
    }
    params = {"q": query, "filter": f"lastSoldDate:[{since}..]", "limit": "1"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers, params=params)
    except Exception as exc:
        log.warning("demand_check.sold_count.request_failed", query=query, error=str(exc))
        return None, "Sold-comp lookup failed (network error)."

    if resp.status_code == 403:
        return None, "Sold-comp data requires eBay Marketplace Insights API access, which this app's credentials are not confirmed to have."
    if resp.status_code != 200:
        log.warning("demand_check.sold_count.bad_status", query=query, status=resp.status_code)
        return None, f"Sold-comp lookup returned {resp.status_code}."

    body = resp.json()
    total = body.get("total")
    return (int(total) if total is not None else 0), None


async def check_demand(cpu: Optional[str], gpu: Optional[str]) -> DemandSignal:
    """Row 10/33: sold-vs-active demand check, fired on build creation."""
    query = build_query(cpu, gpu)
    checked_at = datetime.utcnow()

    token = await _get_app_token()
    if not token:
        return DemandSignal(
            query=query, active_count=None, sold_count_90d=None,
            checked_at=checked_at, sold_data_available=False,
            note="No eBay app token configured — demand check unavailable until eBay API credentials are set.",
        )

    prices = await get_component_prices(query, force_refresh=False, min_price=50.0)
    active_count = len(prices["used_prices"]) + len(prices["new_prices"])

    sold_count, note = await _sold_count_90d(token, query)

    return DemandSignal(
        query=query,
        active_count=active_count,
        sold_count_90d=sold_count,
        checked_at=checked_at,
        sold_data_available=sold_count is not None,
        note=note,
    )
