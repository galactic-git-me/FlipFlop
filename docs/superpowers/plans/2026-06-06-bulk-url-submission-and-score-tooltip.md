# Bulk URL Submission + Flippability Score Tooltip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Bulk URLs tab to the manual submit modal (accepting comma- or newline-separated URLs) and add a hover tooltip to every FlippabilityScore display showing the LLM's per-criteria breakdown.

**Architecture:** Four self-contained changes: (0) fix the backend `manual_scraper.py` to use the eBay Browse API `getItemByLegacyId` endpoint instead of HTML scraping for eBay URLs (HTML scraping is blocked by eBay's bot detection), (1) extend the frontend `Listing` type with already-available `claude_*` fields from the backend, (2) enhance the `FlippabilityScore` component with a Radix UI tooltip that renders the breakdown when claude data is present, (3) add a third "Bulk URLs" tab to `ManualSubmitModal` that sequentially calls the existing `api.manual.submitUrl` endpoint per URL and shows results with the score+tooltip inline.

**Tech Stack:** Python/FastAPI backend (`httpx`, eBay Browse API OAuth client credentials), Next.js 15 (App Router), React, TypeScript, Tailwind CSS, `@radix-ui/react-tooltip` (already installed).

---

## File Map

| Action | File | What changes |
|--------|------|-------------|
| Modify | `pc-flipper-backend/app/services/manual_scraper.py` | Add `_ebay_api_fetch_item()`, update `scrape_url()` to use it |
| Modify | `pc-flipper/lib/types.ts` | Add `claude_*` fields to `Listing` interface |
| Create | `pc-flipper/components/ui/tooltip.tsx` | Radix Tooltip primitives wrapper |
| Modify | `pc-flipper/components/flippability-score.tsx` | Optional `listing` prop + hover breakdown tooltip |
| Modify | `pc-flipper/app/opportunities/page.tsx` | Pass `listing={l}` to `<FlippabilityScore>` at line 434 |
| Modify | `pc-flipper/components/manual-submit-modal.tsx` | Add Bulk URLs tab; update ResultCard to pass listing |

---

## Task 0: Fix manual scraper to use eBay Browse API for eBay URLs

**Context:** The current `scrape_url()` in `manual_scraper.py` fetches the eBay HTML page directly, which eBay blocks with bot detection. The automated pipeline avoids this by using the eBay Browse API (`/buy/browse/v1/item_summary/search`) with OAuth client credentials — the same token machinery is available in `scraper.py`. The Browse API has a `getItemByLegacyId` endpoint that fetches a single listing by the numeric item ID embedded in the URL (e.g., `127844097717` from `https://www.ebay.co.uk/itm/127844097717`).

**Files:**
- Modify: `pc-flipper-backend/app/services/manual_scraper.py`

- [ ] **Step 1: Add `_ebay_api_fetch_item()` function to `manual_scraper.py`**

Add this function after the existing `_parse_ebay_item` function (after line 191):

```python
async def _ebay_api_fetch_item(
    item_id: str, url: str, price_override: Optional[float] = None
) -> "RawListing | None":
    """
    Fetch a single eBay listing via Browse API getItemByLegacyId.
    Returns None if credentials are missing or the API call fails — 
    caller falls back to HTML scraping.
    """
    from app.services.scraper import _get_ebay_access_token, _ebay_base_url

    async with httpx.AsyncClient(timeout=15) as client:
        token = await _get_ebay_access_token(client)
        if not token:
            return None

        endpoint = f"{_ebay_base_url()}/buy/browse/v1/item/get_item_by_legacy_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
            "Content-Type": "application/json",
        }
        resp = await client.get(
            endpoint,
            params={"legacy_item_id": item_id},
            headers=headers,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()

    title = str(data.get("title") or "eBay Listing").strip()

    # Price
    price = price_override
    if price is None:
        price_obj = data.get("price") or data.get("currentBidPrice") or {}
        try:
            price = float(price_obj.get("value") or 0) or None
        except (TypeError, ValueError):
            price = None
    if not price:
        raise ValueError("Could not extract price from eBay API response")

    # Images — primary + additionalImages
    images: list[str] = []
    if primary_url := (data.get("image") or {}).get("imageUrl"):
        images.append(primary_url)
    for extra in data.get("additionalImages") or []:
        if src := extra.get("imageUrl"):
            images.append(src)

    # Location
    loc_obj = data.get("itemLocation") or {}
    location = loc_obj.get("city") or loc_obj.get("country")

    # Description — strip HTML tags
    desc_html = data.get("description") or data.get("shortDescription") or ""
    description = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)[:1000] if desc_html else ""

    # Condition
    condition = data.get("condition")

    # Seller
    seller = data.get("seller") or {}
    seller_name = seller.get("username")
    feedback_score: Optional[int] = None
    try:
        feedback_score = int(seller.get("feedbackScore") or 0) or None
    except (TypeError, ValueError):
        pass
    feedback_pct: Optional[float] = None
    try:
        pct_str = str(seller.get("feedbackPercentage") or "")
        feedback_pct = float(pct_str.replace("%", "")) if pct_str else None
    except (TypeError, ValueError):
        pass

    # Listing type
    buying_options = data.get("buyingOptions") or []
    listing_type = "auction" if "AUCTION" in buying_options else "buy_it_now"

    # Auction end datetime
    listing_ends_at = None
    if end_date_str := data.get("itemEndDate"):
        try:
            listing_ends_at = datetime.fromisoformat(
                end_date_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            pass

    from app.services.scraper import classify_seller

    return RawListing(
        external_id=f"ebay_{item_id}",
        title=title,
        price=price,
        url=url,
        location=location,
        condition=condition,
        description=description,
        image_urls=images[:5],
        source_name="Manual Submission",
        source_confidence="official_api",
        listing_type=listing_type,
        listing_ends_at=listing_ends_at,
        seller_name=seller_name,
        seller_feedback_count=feedback_score,
        seller_feedback_pct=feedback_pct,
        seller_type=classify_seller(seller_name, feedback_score, title),
    )
```

- [ ] **Step 2: Replace `scrape_url()` to try the API first for eBay URLs**

Replace the existing `scrape_url` function (lines 48–74) with:

```python
async def scrape_url(url: str, price_override: Optional[float] = None) -> RawListing:
    """
    Fetch a listing URL and return a RawListing.
    For eBay URLs: tries the Browse API first (bot-safe), falls back to HTML.
    Raises ValueError if the page can't be parsed sensibly.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "ebay.co.uk" in host or "ebay.com" in host:
        item_id_match = re.search(r"/itm/(?:[^/]+/)?(\d+)", url)
        if item_id_match:
            try:
                result = await _ebay_api_fetch_item(
                    item_id_match.group(1), url, price_override
                )
                if result:
                    return result
            except ValueError:
                raise  # price-not-found errors should surface to the caller
            except Exception:
                pass  # network / auth failure → fall through to HTML scraping

        # HTML fallback (e.g. no eBay credentials configured)
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=15
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                raise ValueError(f"HTTP {resp.status_code} fetching {url}")
        return _parse_ebay_item(resp.text, url, price_override)

    # Non-eBay: HTML scraping
    async with httpx.AsyncClient(
        headers=_HEADERS, follow_redirects=True, timeout=15
    ) as client:
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise ValueError(f"HTTP {resp.status_code} fetching {url}")
        html = resp.text

    if "gumtree.com" in host:
        return _parse_gumtree_item(html, url, price_override)
    if "preloved.co.uk" in host:
        return _parse_preloved_item(html, url, price_override)
    if "facebook.com" in host or "fb.com" in host:
        return _parse_facebook_item(html, url, price_override)
    return _parse_generic(html, url, price_override)
```

- [ ] **Step 3: Verify imports — confirm `BeautifulSoup` is already imported at the top of `manual_scraper.py`**

Check line 23 of `manual_scraper.py` — it should already have `from bs4 import BeautifulSoup`. If not, add it. The `datetime` import is also needed and is already present at line 16.

- [ ] **Step 4: Restart the backend and do a quick smoke test**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-backend
# If running in venv:
source .venv/bin/activate 2>/dev/null || true
python -c "
import asyncio
from app.services.manual_scraper import scrape_url
result = asyncio.run(scrape_url('https://www.ebay.co.uk/itm/127844097717'))
print('Title:', result.title)
print('Price:', result.price)
print('Source confidence:', result.source_confidence)
"
```

Expected: prints a title and price, `source_confidence` is `official_api` if eBay credentials are configured, or `browser_verified` if falling back to HTML.

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-backend/app/services/manual_scraper.py
git commit -m "fix: use eBay Browse API for manual URL submission (avoids bot detection)"
```

---

## Task 1: Add claude_* fields to the Listing TypeScript interface

The backend's `ListingOut` Pydantic schema already returns all these fields. The frontend just doesn't have them typed yet.

**Files:**
- Modify: `pc-flipper/lib/types.ts` (lines 14–54, the `Listing` interface)

- [ ] **Step 1: Open `pc-flipper/lib/types.ts` and add the claude fields to `Listing`**

Find the `Listing` interface (starts at line 14) and add these fields at the end, before the closing `}`:

```typescript
export interface Listing {
  id: number;
  external_id: string;
  source_name: string;
  title: string;
  price: number;
  url: string;
  image_urls: string[];
  location: string | null;
  condition: string | null;
  cpu: string | null;
  ram_gb: number | null;
  ram_type: string | null;
  storage_gb: number | null;
  storage_type: string | null;
  gpu: string | null;
  has_psu: boolean;
  gem_score: number;
  classification: Classification;
  gem_signals: string[];
  estimated_resale: number | null;
  estimated_upgrade_cost: number | null;
  resale_low: number | null;
  resale_high: number | null;
  resale_comp_count: number | null;
  estimated_profit: number | null;
  listing_type: "auction" | "buy_it_now" | "classified" | null;
  listing_ends_at: string | null;
  expected_buy_price: number | null;
  seller_name: string | null;
  seller_feedback_count: number | null;
  seller_feedback_pct: number | null;
  seller_type: "shop" | "refurb_shop" | "flipper" | "private" | null;
  seller_has_shop: boolean;
  listed_at: string | null;
  status: ListingStatus;
  first_seen_at: string;
  last_seen_at: string;
  // Claude LLM evaluation (populated asynchronously after initial save)
  claude_verdict:            string | null;
  claude_flipability_score:  number | null;
  claude_expected_profit:    number | null;
  claude_roi:                number | null;
  claude_confidence:         number | null;
  claude_capital_efficiency: number | null;
  claude_resale_demand:      number | null;
  claude_upgrade_complexity: number | null;
  claude_reasoning:          string | null;
  claude_main_risk:          string | null;
  claude_judged_at:          string | null;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors, or only pre-existing errors unrelated to these new fields.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
git add lib/types.ts
git commit -m "feat: add claude_* fields to Listing TypeScript interface"
```

---

## Task 2: Create the Radix UI Tooltip wrapper component

`@radix-ui/react-tooltip` is already in `package.json`. We need a thin wrapper in the `components/ui/` folder that matches the existing shadcn-style component conventions.

**Files:**
- Create: `pc-flipper/components/ui/tooltip.tsx`

- [ ] **Step 1: Create `pc-flipper/components/ui/tooltip.tsx`**

```typescript
"use client";

import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 max-w-xs rounded-xl border border-[#1e2d45] bg-[#080f1a] px-0 py-0 text-slate-100 shadow-2xl shadow-black/60",
        "data-[state=delayed-open]:animate-in data-[state=closed]:animate-out",
        "data-[state=closed]:fade-out-0 data-[state=delayed-open]:fade-in-0",
        "data-[state=closed]:zoom-out-95 data-[state=delayed-open]:zoom-in-95",
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent };
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
git add components/ui/tooltip.tsx
git commit -m "feat: add Radix UI Tooltip wrapper component"
```

---

## Task 3: Enhance FlippabilityScore with hover breakdown tooltip

The component grows from a pure display widget into one that, when given a `listing` prop containing claude data, wraps itself in a tooltip showing the per-criteria breakdown table.

**Score mapping** (derived from claude fields):
- **Gaming demand** → `claude_resale_demand` (1–10, direct)
- **Ease of resale** → `claude_capital_efficiency` (1–10, direct)
- **Upgrade potential** → `11 - claude_upgrade_complexity` (inverts complexity: 1=simple → 10 potential)
- **Profit potential** → `Math.min(10, Math.max(1, Math.round((claude_roi ?? 0) * 10)))` (ROI 0.8 → 8/10)

The overall score shown in the tooltip is `claude_flipability_score` (0–100), displayed as `X/10` via `/10`.

If claude data is absent (listing not yet evaluated), show "AI evaluation pending" instead of the breakdown.

**Files:**
- Modify: `pc-flipper/components/flippability-score.tsx`

- [ ] **Step 1: Replace the full content of `pc-flipper/components/flippability-score.tsx`**

```typescript
"use client";

import { SCORE_TIER } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { Listing } from "@/lib/types";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface Props {
  score: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  listing?: Listing | null;
}

function ScoreBreakdown({ listing }: { listing: Listing }) {
  const hasData =
    listing.claude_resale_demand != null &&
    listing.claude_capital_efficiency != null &&
    listing.claude_upgrade_complexity != null;

  const verdictColors: Record<string, string> = {
    GEM:    "text-cyan-400 bg-cyan-400/10 border-cyan-400/30",
    GOOD:   "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
    MAYBE:  "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
    REJECT: "text-red-400 bg-red-400/10 border-red-400/30",
  };
  const verdictStyle = listing.claude_verdict
    ? (verdictColors[listing.claude_verdict] ?? verdictColors.MAYBE)
    : "";

  const profitPotential = listing.claude_roi != null
    ? Math.min(10, Math.max(1, Math.round(listing.claude_roi * 10)))
    : null;

  const upgradePotential = listing.claude_upgrade_complexity != null
    ? 11 - listing.claude_upgrade_complexity
    : null;

  const criteria = [
    { label: "Gaming demand",      value: listing.claude_resale_demand },
    { label: "Ease of resale",     value: listing.claude_capital_efficiency },
    { label: "Upgrade potential",  value: upgradePotential },
    { label: "Profit potential",   value: profitPotential },
  ];

  function barColor(v: number): string {
    if (v >= 8) return "bg-cyan-400";
    if (v >= 6) return "bg-emerald-400";
    if (v >= 4) return "bg-yellow-400";
    return "bg-red-400";
  }

  if (!hasData) {
    return (
      <div className="px-3 py-3 text-xs text-slate-500 italic">
        AI evaluation pending…
      </div>
    );
  }

  return (
    <div className="w-64">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 border-b border-[#1e2d45]">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Flippability Breakdown
        </span>
        {listing.claude_verdict && (
          <span className={cn(
            "text-[10px] font-bold px-2 py-0.5 rounded-full border",
            verdictStyle,
          )}>
            {listing.claude_verdict}
          </span>
        )}
      </div>

      {/* Criteria rows */}
      <div className="px-3 py-2 space-y-2">
        {criteria.map(({ label, value }) => (
          value != null && (
            <div key={label} className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400 w-32 flex-shrink-0">{label}</span>
              <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all", barColor(value))}
                  style={{ width: `${value * 10}%` }}
                />
              </div>
              <span className="text-[11px] font-semibold text-slate-200 w-8 text-right flex-shrink-0">
                {value}/10
              </span>
            </div>
          )
        ))}
      </div>

      {/* Overall score */}
      {listing.claude_flipability_score != null && (
        <div className="flex items-center justify-between px-3 pt-1.5 pb-2 border-t border-[#1e2d45] mt-1">
          <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">
            Flipability
          </span>
          <span className="text-sm font-black text-[#00dc82]">
            {(listing.claude_flipability_score / 10).toFixed(1)}/10
          </span>
        </div>
      )}

      {/* Reasoning */}
      {listing.claude_reasoning && (
        <div className="px-3 pb-2.5 border-t border-[#1e2d45] pt-2">
          <p className="text-[11px] text-slate-400 leading-relaxed">
            {listing.claude_reasoning}
          </p>
        </div>
      )}

      {/* Main risk */}
      {listing.claude_main_risk && (
        <div className="px-3 pb-3">
          <p className="text-[10px] text-amber-400/80">
            ⚠ {listing.claude_main_risk}
          </p>
        </div>
      )}
    </div>
  );
}

export function FlippabilityScore({
  score,
  size = "md",
  showLabel = true,
  listing,
}: Props) {
  const tier = SCORE_TIER(score);
  const sizes = {
    sm: "w-8 h-8 text-sm",
    md: "w-11 h-11 text-base",
    lg: "w-14 h-14 text-xl",
  };

  const badge = (
    <div className="flex flex-col items-center gap-0.5 cursor-default">
      <div className={cn(
        "rounded-xl border flex items-center justify-center font-black ring-1",
        sizes[size],
        tier.bg,
        tier.color,
        tier.ring,
      )}>
        {tier.label}
      </div>
      {showLabel && (
        <div className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">
          {score.toFixed(0)}<span className="opacity-50">/100</span>
        </div>
      )}
    </div>
  );

  if (!listing) return badge;

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent side="right" align="center">
          <ScoreBreakdown listing={listing} />
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
git add components/flippability-score.tsx
git commit -m "feat: add LLM breakdown hover tooltip to FlippabilityScore component"
```

---

## Task 4: Wire listing prop into FlippabilityScore on the Opportunities page

The `ListingRow` component in `app/opportunities/page.tsx` already has `listing={l}` available. Just pass it through to `FlippabilityScore`.

**Files:**
- Modify: `pc-flipper/app/opportunities/page.tsx` (line 434)

- [ ] **Step 1: Find line 434 and update the FlippabilityScore call**

Current (line 434):
```tsx
<FlippabilityScore score={l.gem_score} size="lg" />
```

Replace with:
```tsx
<FlippabilityScore score={l.gem_score} size="lg" listing={l} />
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
git add app/opportunities/page.tsx
git commit -m "feat: pass listing to FlippabilityScore on opportunities page"
```

---

## Task 5: Add Bulk URLs tab to ManualSubmitModal

Adds a third tab "Bulk URLs" to the existing modal. The tab accepts a textarea of URLs in any format (comma-separated, newline-separated, or both). Clicking "Process All" iterates through each URL sequentially, calling the existing `api.manual.submitUrl()` endpoint, updating per-URL status in real time. When all URLs are done, the results section renders each listing's title, price, classification, and `FlippabilityScore` (with tooltip).

URL parsing logic: `input.split(/[\n,]+/).map(u => u.trim()).filter(u => u.startsWith("http"))`

**Files:**
- Modify: `pc-flipper/components/manual-submit-modal.tsx`

- [ ] **Step 1: Replace the full content of `pc-flipper/components/manual-submit-modal.tsx`**

```typescript
"use client";
/* eslint-disable @next/next/no-img-element */

import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Link2, Camera, X, Upload, RefreshCw, CheckCircle, AlertCircle,
  Gem, List, Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { Listing } from "@/lib/types";
import { CLASSIFICATION_CONFIG, SCORE_TIER } from "@/lib/types";
import { FlippabilityScore } from "@/components/flippability-score";
import { formatCurrency } from "@/lib/utils";

type Tab = "url" | "photo" | "bulk";
type State = "idle" | "loading" | "success" | "error";

// ── Single-listing result card (used by URL and photo tabs) ───────────────────

function ResultCard({ listing }: { listing: Listing }) {
  const cls  = CLASSIFICATION_CONFIG[listing.classification] ?? CLASSIFICATION_CONFIG.unclassified;
  const profit = listing.estimated_profit ?? 0;

  return (
    <div className="rounded-xl border border-[#1e2d45] bg-[#0d1726] overflow-hidden">
      <div className="flex gap-3 p-3">
        <div className="w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-[#080c14]">
          {listing.image_urls?.[0] ? (
            <img src={listing.image_urls[0]} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center opacity-20">
              <Gem className="w-7 h-7 text-slate-400" />
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          {listing.url ? (
            <a href={listing.url} target="_blank" rel="noopener noreferrer"
              className="text-sm font-semibold text-slate-100 line-clamp-2 hover:text-[#00dc82] transition-colors block">
              {listing.title}
            </a>
          ) : (
            <p className="text-sm font-semibold text-slate-100 line-clamp-2">{listing.title}</p>
          )}
          <div className="flex flex-wrap gap-1 mt-1.5">
            {[listing.cpu, listing.ram_gb && `${listing.ram_gb}GB`, listing.gpu].filter(Boolean).map((s, i) => (
              <span key={i} className="text-[10px] text-slate-400 bg-white/[0.05] border border-white/[0.07] rounded px-1.5 py-0.5">{s}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x divide-[#1e2d45] border-t border-[#1e2d45]">
        <div className="px-3 py-2 text-center">
          <div className="text-xs text-slate-500">Buy Price</div>
          <div className="text-sm font-bold text-slate-200">{formatCurrency(listing.price)}</div>
        </div>
        <div className="px-3 py-2 text-center">
          <div className="text-xs text-slate-500">Est. Resale</div>
          <div className="text-sm font-bold text-slate-200">{listing.estimated_resale ? formatCurrency(listing.estimated_resale) : "—"}</div>
        </div>
        <div className="px-3 py-2 text-center">
          <div className="text-xs text-slate-500">Est. Profit</div>
          <div className={`text-sm font-bold ${profit > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
            {profit > 0 ? "+" : ""}{formatCurrency(profit)}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 px-3 py-2 border-t border-[#1e2d45]">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cls.bg} ${cls.color}`}>
          {cls.emoji} {cls.label}
        </span>
        <FlippabilityScore score={listing.gem_score} size="sm" showLabel={false} listing={listing} />
        <span className="text-xs text-slate-500 ml-1">{listing.gem_score.toFixed(0)}/100</span>
        {listing.gem_signals?.length > 0 && (
          <span className="text-[10px] text-slate-500 ml-auto">
            {listing.gem_signals.slice(0, 3).join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Bulk URL result row ────────────────────────────────────────────────────────

interface BulkItem {
  url: string;
  status: "pending" | "loading" | "success" | "error";
  listing?: Listing;
  error?: string;
}

function BulkRow({ item }: { item: BulkItem }) {
  const cls = item.listing
    ? (CLASSIFICATION_CONFIG[item.listing.classification] ?? CLASSIFICATION_CONFIG.unclassified)
    : null;

  return (
    <div className={`rounded-xl border overflow-hidden transition-colors ${
      item.status === "success" ? "border-[#1e2d45] bg-[#0d1726]" :
      item.status === "error"   ? "border-red-500/20 bg-red-500/5" :
      "border-[#1e2d45] bg-[#0a1119]"
    }`}>
      {/* Status bar */}
      <div className="flex items-center gap-2.5 px-3 py-2">
        <div className="flex-shrink-0">
          {item.status === "pending" && <div className="w-4 h-4 rounded-full border border-slate-600" />}
          {item.status === "loading" && <Loader2 className="w-4 h-4 text-[#00dc82] animate-spin" />}
          {item.status === "success" && <CheckCircle className="w-4 h-4 text-[#00dc82]" />}
          {item.status === "error"   && <AlertCircle className="w-4 h-4 text-red-400" />}
        </div>
        <span className="text-[11px] text-slate-500 truncate flex-1 font-mono">
          {item.url.replace(/^https?:\/\/(www\.)?/, "").slice(0, 60)}
        </span>
      </div>

      {/* Success: listing details */}
      {item.status === "success" && item.listing && (
        <div className="border-t border-[#1e2d45] px-3 py-2 flex items-center gap-3">
          <FlippabilityScore score={item.listing.gem_score} size="sm" showLabel={false} listing={item.listing} />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-200 line-clamp-1">{item.listing.title}</p>
            <div className="flex items-center gap-2 mt-0.5">
              {cls && (
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full border ${cls.bg} ${cls.color}`}>
                  {cls.emoji} {cls.label}
                </span>
              )}
              <span className="text-[10px] text-slate-500">{formatCurrency(item.listing.price)}</span>
              {item.listing.estimated_profit != null && (
                <span className={`text-[10px] font-semibold ${item.listing.estimated_profit > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
                  {item.listing.estimated_profit > 0 ? "+" : ""}{formatCurrency(item.listing.estimated_profit)} profit
                </span>
              )}
            </div>
          </div>
          <span className="text-xs font-black text-slate-400 flex-shrink-0">
            {item.listing.gem_score.toFixed(0)}
            <span className="text-slate-600 font-normal">/100</span>
          </span>
        </div>
      )}

      {/* Error message */}
      {item.status === "error" && item.error && (
        <div className="border-t border-red-500/20 px-3 py-1.5">
          <p className="text-[11px] text-red-400/80">{item.error}</p>
        </div>
      )}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess?: (listing: Listing) => void;
}

export function ManualSubmitModal({ open, onClose, onSuccess }: Props) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("url");
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string>("");
  const [result, setResult] = useState<Listing | null>(null);

  // URL tab
  const [url, setUrl] = useState("");
  const [priceOverride, setPriceOverride] = useState("");

  // Photo tab
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string>("");
  const [photoTitle, setPhotoTitle] = useState("");
  const [photoPrice, setPhotoPrice] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Bulk tab
  const [bulkInput, setBulkInput] = useState("");
  const [bulkItems, setBulkItems] = useState<BulkItem[]>([]);
  const [bulkRunning, setBulkRunning] = useState(false);

  const reset = useCallback(() => {
    setState("idle");
    setError("");
    setResult(null);
    setUrl("");
    setPriceOverride("");
    setImageFile(null);
    setImagePreview("");
    setPhotoTitle("");
    setPhotoPrice("");
    setBulkInput("");
    setBulkItems([]);
    setBulkRunning(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleImageFile = (file: File) => {
    if (!file.type.startsWith("image/")) return;
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = e => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleImageFile(file);
  }, []);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) handleImageFile(file);
        break;
      }
    }
  }, []);

  const submitUrl = async () => {
    if (!url.trim()) return;
    setState("loading");
    setError("");
    try {
      const override = priceOverride ? parseFloat(priceOverride) : undefined;
      const listing = await api.manual.submitUrl(url.trim(), override);
      setResult(listing);
      setState("success");
      onSuccess?.(listing);
    } catch (e: unknown) {
      setState("error");
      setError(e instanceof Error ? e.message : "Submission failed");
    }
  };

  const submitImage = async () => {
    if (!imageFile) return;
    if (!photoPrice && !imageFile) return;
    setState("loading");
    setError("");
    try {
      const price = photoPrice ? parseFloat(photoPrice) : undefined;
      const listing = await api.manual.submitImage(imageFile, photoTitle || undefined, price);
      setResult(listing);
      setState("success");
      onSuccess?.(listing);
    } catch (e: unknown) {
      setState("error");
      setError(e instanceof Error ? e.message : "Submission failed");
    }
  };

  // Parse URLs from the textarea: split on commas and/or newlines, trim, keep http(s) only
  const parseBulkUrls = (input: string): string[] =>
    input.split(/[\n,]+/).map(u => u.trim()).filter(u => u.startsWith("http"));

  const submitBulk = async () => {
    const urls = parseBulkUrls(bulkInput);
    if (urls.length === 0) return;

    // Initialise all items as pending
    const initial: BulkItem[] = urls.map(u => ({ url: u, status: "pending" }));
    setBulkItems(initial);
    setBulkRunning(true);

    for (let i = 0; i < urls.length; i++) {
      // Mark this one as loading
      setBulkItems(prev =>
        prev.map((item, idx) => idx === i ? { ...item, status: "loading" } : item)
      );

      try {
        const listing = await api.manual.submitUrl(urls[i]);
        onSuccess?.(listing);
        setBulkItems(prev =>
          prev.map((item, idx) =>
            idx === i ? { ...item, status: "success", listing } : item
          )
        );
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : "Failed";
        setBulkItems(prev =>
          prev.map((item, idx) =>
            idx === i ? { ...item, status: "error", error: errMsg } : item
          )
        );
      }
    }

    setBulkRunning(false);
  };

  const bulkUrls = parseBulkUrls(bulkInput);
  const bulkDone = bulkItems.length > 0 && !bulkRunning;
  const bulkSuccessCount = bulkItems.filter(i => i.status === "success").length;
  const bulkErrorCount = bulkItems.filter(i => i.status === "error").length;

  const goToOpportunities = () => {
    handleClose();
    router.push("/opportunities");
  };

  const goToBuildWizard = () => {
    if (!result) return;
    handleClose();
    router.push(`/chat?listing_id=${result.id}`);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onPaste={handlePaste}
    >
      <div className="w-full max-w-lg bg-[#0d1726] border border-[#1e2d45] rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e2d45] flex-shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Submit a Listing</h2>
            <p className="text-xs text-slate-500 mt-0.5">URL or photo → full pipeline analysis in seconds</p>
          </div>
          <button
            onClick={handleClose}
            className="text-slate-500 hover:text-slate-200 p-1 rounded-lg hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-3 pb-0 flex-shrink-0">
          {([
            { key: "url"   as Tab, label: "Paste a URL",  Icon: Link2  },
            { key: "photo" as Tab, label: "Upload Photo", Icon: Camera },
            { key: "bulk"  as Tab, label: "Bulk URLs",    Icon: List   },
          ] as const).map(({ key, label, Icon }) => (
            <button
              key={key}
              onClick={() => { setTab(key); setError(""); }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === key
                  ? "bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/20"
                  : "text-slate-500 hover:text-slate-300 border border-transparent"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1">
          <div className="p-5 space-y-4">

            {/* ── URL tab ── */}
            {tab === "url" && state !== "success" && (
              <>
                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">Listing URL</label>
                  <input
                    value={url}
                    onChange={e => setUrl(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && submitUrl()}
                    placeholder="https://www.ebay.co.uk/itm/... or gumtree.com/..."
                    disabled={state === "loading"}
                    className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50"
                  />
                  <p className="text-[10px] text-slate-600 mt-1">
                    Supports eBay, Gumtree, Preloved, Facebook Marketplace, and most listing sites.
                  </p>
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">
                    Price override <span className="text-slate-600">(optional — leave blank to auto-detect)</span>
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">£</span>
                    <input
                      type="number"
                      value={priceOverride}
                      onChange={e => setPriceOverride(e.target.value)}
                      placeholder="e.g. 149"
                      disabled={state === "loading"}
                      className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg pl-7 pr-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50"
                    />
                  </div>
                </div>
              </>
            )}

            {/* ── Photo tab ── */}
            {tab === "photo" && state !== "success" && (
              <>
                <div
                  onDragOver={e => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => fileRef.current?.click()}
                  className={`relative rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
                    dragging ? "border-[#00dc82] bg-[#00dc82]/5" :
                    imagePreview ? "border-[#1e2d45]" : "border-[#1e2d45] hover:border-[#2a3d5c]"
                  }`}
                >
                  {imagePreview ? (
                    <div className="relative">
                      <img src={imagePreview} alt="Preview" className="w-full max-h-52 object-contain rounded-xl" />
                      <button
                        onClick={e => { e.stopPropagation(); setImageFile(null); setImagePreview(""); }}
                        className="absolute top-2 right-2 bg-black/60 rounded-full p-1 text-white hover:bg-black/80 transition-colors"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-10 gap-2 text-slate-500">
                      <Upload className="w-8 h-8 opacity-40" />
                      <p className="text-sm">Drop photo here, click to browse, or <kbd className="text-xs bg-white/10 px-1 rounded">Ctrl+V</kbd> to paste</p>
                      <p className="text-xs text-slate-600">JPEG, PNG, WebP — max 15 MB</p>
                    </div>
                  )}
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleImageFile(f); }}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-400 block mb-1.5">
                      Title / description <span className="text-slate-600">(optional)</span>
                    </label>
                    <input
                      value={photoTitle}
                      onChange={e => setPhotoTitle(e.target.value)}
                      placeholder="e.g. Dell OptiPlex i7 no GPU"
                      disabled={state === "loading"}
                      className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1.5">
                      Price <span className="text-[#00dc82]">*</span>
                    </label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">£</span>
                      <input
                        type="number"
                        value={photoPrice}
                        onChange={e => setPhotoPrice(e.target.value)}
                        placeholder="e.g. 80"
                        disabled={state === "loading"}
                        className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg pl-7 pr-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50"
                      />
                    </div>
                  </div>
                </div>
                {!photoPrice && (
                  <p className="text-[10px] text-amber-400/70">
                    ⚠ Price is required for photo submissions (AI may not be able to read it from the image).
                  </p>
                )}
              </>
            )}

            {/* ── Bulk URLs tab ── */}
            {tab === "bulk" && (
              <>
                {bulkItems.length === 0 ? (
                  /* Input phase */
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1.5">
                        Paste URLs
                        <span className="text-slate-600 ml-1">(comma-separated or one per line)</span>
                      </label>
                      <textarea
                        value={bulkInput}
                        onChange={e => setBulkInput(e.target.value)}
                        placeholder={`https://www.ebay.co.uk/itm/123, https://www.ebay.co.uk/itm/456\n\nor one per line`}
                        rows={5}
                        className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none resize-none font-mono"
                      />
                    </div>
                    {bulkUrls.length > 0 && (
                      <p className="text-[11px] text-[#00dc82]/70">
                        {bulkUrls.length} URL{bulkUrls.length !== 1 ? "s" : ""} detected
                      </p>
                    )}
                  </div>
                ) : (
                  /* Results phase */
                  <div className="space-y-2.5">
                    {/* Summary bar */}
                    {bulkDone && (
                      <div className="flex items-center gap-2 py-2 text-xs">
                        <CheckCircle className="w-3.5 h-3.5 text-[#00dc82]" />
                        <span className="text-[#00dc82] font-semibold">{bulkSuccessCount} processed</span>
                        {bulkErrorCount > 0 && (
                          <span className="text-red-400">{bulkErrorCount} failed</span>
                        )}
                        <button
                          onClick={() => { setBulkItems([]); setBulkInput(""); }}
                          className="ml-auto text-slate-500 hover:text-slate-300 transition-colors"
                        >
                          ← Submit another batch
                        </button>
                      </div>
                    )}
                    {bulkRunning && (
                      <div className="flex items-center gap-2 py-1 text-xs text-slate-500">
                        <RefreshCw className="w-3 h-3 animate-spin text-[#00dc82]" />
                        Processing {bulkItems.filter(i => i.status !== "pending").length} of {bulkItems.length}…
                      </div>
                    )}
                    {bulkItems.map((item, idx) => (
                      <BulkRow key={idx} item={item} />
                    ))}
                  </div>
                )}
              </>
            )}

            {/* ── Single URL/photo result ── */}
            {state === "success" && result && tab !== "bulk" && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium text-[#00dc82]">
                  <CheckCircle className="w-4 h-4" />
                  Listing analysed and added to your database
                </div>
                <ResultCard listing={result} />
              </div>
            )}

            {/* ── Error ── */}
            {state === "error" && (
              <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-sm text-red-400">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Submission failed</p>
                  <p className="text-xs mt-0.5 text-red-400/70">{error}</p>
                </div>
              </div>
            )}

            {/* ── Loading indicator (URL / photo tabs) ── */}
            {state === "loading" && (
              <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[#111c2e] border border-[#1e2d45] text-sm text-slate-400">
                <RefreshCw className="w-4 h-4 animate-spin text-[#00dc82]" />
                <span>
                  {tab === "url" ? "Fetching page & running pipeline…" : "Analysing photo with AI vision…"}
                </span>
                <span className="text-xs text-slate-600 ml-auto">up to 30s</span>
              </div>
            )}

          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center gap-2 px-5 py-4 border-t border-[#1e2d45] flex-shrink-0">
          {/* ── Bulk tab footer ── */}
          {tab === "bulk" && (
            <>
              <Button variant="ghost" onClick={handleClose} className="text-slate-400">
                {bulkDone ? "Close" : "Cancel"}
              </Button>
              {bulkDone ? (
                <Button
                  onClick={goToOpportunities}
                  className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold"
                >
                  View in Opportunities →
                </Button>
              ) : (
                <Button
                  onClick={submitBulk}
                  disabled={bulkRunning || bulkUrls.length === 0}
                  className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold disabled:opacity-50"
                >
                  {bulkRunning ? (
                    <><RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing…</>
                  ) : (
                    `Analyse ${bulkUrls.length > 0 ? bulkUrls.length : ""} URL${bulkUrls.length !== 1 ? "s" : ""}`
                  )}
                </Button>
              )}
            </>
          )}

          {/* ── URL / Photo tab footer ── */}
          {tab !== "bulk" && (
            <>
              {state === "success" ? (
                <>
                  <Button variant="ghost" onClick={reset} className="text-slate-400">Submit another</Button>
                  <Button
                    variant="ghost"
                    onClick={goToBuildWizard}
                    className="text-[#00dc82] border border-[#00dc82]/30 hover:bg-[#00dc82]/10"
                  >
                    Build system from this →
                  </Button>
                  <Button
                    onClick={goToOpportunities}
                    className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold"
                  >
                    View in Opportunities →
                  </Button>
                </>
              ) : state === "error" ? (
                <>
                  <Button variant="ghost" onClick={() => setState("idle")} className="text-slate-400">Try again</Button>
                  <Button variant="ghost" onClick={handleClose} className="ml-auto text-slate-400">Close</Button>
                </>
              ) : (
                <>
                  <Button variant="ghost" onClick={handleClose} className="text-slate-400" disabled={state === "loading"}>
                    Cancel
                  </Button>
                  {tab === "url" ? (
                    <Button
                      onClick={submitUrl}
                      disabled={state === "loading" || !url.trim()}
                      className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold"
                    >
                      {state === "loading" ? <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
                      Analyse URL
                    </Button>
                  ) : (
                    <Button
                      onClick={submitImage}
                      disabled={state === "loading" || !imageFile || !photoPrice}
                      className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold"
                    >
                      {state === "loading" ? <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
                      Analyse Photo
                    </Button>
                  )}
                </>
              )}
            </>
          )}
        </div>

      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors.

- [ ] **Step 3: Do a full build to catch any Next.js-specific issues**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper && npm run build 2>&1 | tail -30
```

Expected: `✓ Compiled successfully` or equivalent success output. Fix any errors before committing.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper
git add components/manual-submit-modal.tsx
git commit -m "feat: add Bulk URLs tab to ManualSubmitModal with per-URL progress and results"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Bulk URL paste (comma-separated format from user): handled by `parseBulkUrls` splitting on `/[\n,]+/`
- ✅ URLs added to pipeline "just like automated process": calls `api.manual.submitUrl()` — same endpoint as single URL tab
- ✅ Modal popup showing flippability scores: `BulkRow` renders `FlippabilityScore` + score + classification per item within the modal
- ✅ Flippability score hover tooltip: Task 3 builds `ScoreBreakdown` with the four criteria from the screenshot
- ✅ Breakdown shows criteria + scores: Gaming demand, Ease of resale, Upgrade potential, Profit potential each as X/10
- ✅ `claude_*` fields in frontend types: Task 1

**Score mapping confirmation:**
- Gaming demand → `claude_resale_demand` (1–10, direct from LLM)
- Ease of resale → `claude_capital_efficiency` (1–10, direct from LLM)
- Upgrade potential → `11 - claude_upgrade_complexity` (inverted: complexity 1=simple → potential 10)
- Profit potential → `Math.min(10, Math.max(1, Math.round(claude_roi * 10)))` — ROI 0.8 → 8/10

**Placeholder scan:** None found. All code is complete.

**Type consistency check:**
- `BulkItem` defined before use ✅
- `FlippabilityScore` new `listing` prop: optional `Listing | null` ✅
- `ScoreBreakdown` takes `listing: Listing` (non-null, checked at call site) ✅
- All `claude_*` field names match between Task 1 (types.ts) and Task 3 (flippability-score.tsx) ✅
