# Demand Explorer Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dedicated `/demand` page that lets the user slice, explore and visualise all demand data in one place — category signals, external signals (Reddit/Google/Steam), and live auction intel.

**Architecture:** Single Next.js page at `app/demand/page.tsx`. Three tabs (Categories / External Signals / Auction Intel), each with a Recharts bar chart and a sortable/filterable table beneath it. All data fetched client-side from existing backend endpoints. Sidebar nav link added to `components/sidebar.tsx`. No new backend endpoints needed.

**Tech Stack:** Next.js 14 (app router, `"use client"`), Recharts, Tailwind / existing CSS vars, Lucide icons, existing `api` helper in `lib/api.ts`.

---

## Data sources (existing endpoints)

| Endpoint | Used by tab | Key fields |
|---|---|---|
| `GET /demand/categories` | Categories | name, emoji, count, gem_count, sparkline[7], trend, strength, avg_profit, avg_price, insight |
| `GET /demand/external-signals` | External Signals | source (reddit/google_trends/steam_hardware), topic, query, score, confidence, sample_size, signal_time, notes |
| `GET /demand/auction-intel?limit=50` | Auction Intel | id, title, url, price, estimated_profit, gem_score, classification, listing_ends_at, time_left_secs, urgency (ending_soon/today/upcoming), cpu, gpu |
| `GET /demand/summary` | Header KPIs | market_health, total_gems, gem_rate_pct, rising_count, falling_count, hottest_category |

---

## Page structure

```
/demand
├── Header row
│   ├── "Demand Explorer" title + TrendingUp icon
│   ├── Market health badge (hot 🔥 / warm / cold)
│   ├── KPI chips: total gems · gem rate · rising/falling counts
│   └── Refresh button (re-fetches all four endpoints)
│
├── Tab bar
│   ├── 📦 Categories  (default)
│   ├── 📡 External Signals
│   └── ⏱ Auction Intel
│
└── Tab content (see per-tab spec below)
```

---

## Tab 1 — Categories

### Slicers (above chart)
- **Strength** pill filter: All · High · Medium · Low
- **Trend** pill filter: All · Rising · Stable · Falling
- **Sort** dropdown: Count ↓ · Gem Count ↓ · Avg Profit ↓ · Avg Price ↓
- **Chart metric** toggle buttons: `Listings` | `Avg Profit`

### Chart
- `BarChart` (Recharts, responsive, 260px height)
- X-axis: category name (emoji + short name)
- Y-axis: count (Listings mode) or £ (Avg Profit mode)
- Bar fill colour by strength: `#00dc82` (High) · `#f59e0b` (Medium) · `#ef4444` (Low)
- Tooltip: name, strength, count, gem_count, avg_profit, trend

### Table columns
| Column | Value | Notes |
|---|---|---|
| Category | emoji + name | |
| Strength | coloured badge | High/Medium/Low |
| Trend | icon + label | 📈 rising / → stable / 📉 falling |
| Listings | count | sortable |
| Gems | gem_count | green text |
| Gem Rate | gem_count/count % | |
| Avg Profit | avg_profit | green/amber |
| Avg Price | avg_price | |
| Insight | insight string | truncated, full on hover |
| Sparkline | inline mini bar chart (7 days) | 60px wide, rendered in cell |

Rows sorted by current sort selection. Filtered by Strength + Trend slicers. Click row → no action (read-only explorer).

---

## Tab 2 — External Signals

### Slicers
- **Source** pill filter: All · Reddit · Google Trends · Steam
- **Topic** pill filter: All · am5_bundles · midrange_gpu · workstation_cpu · pc_intent
- **Sort** dropdown: Score ↓ · Confidence ↓ · Date ↓

### Chart
- Grouped `BarChart` (Recharts, responsive, 220px height)
- X-axis: topic
- Each group has 3 bars — one per source
- Bar colours: Reddit `#ff6b6b` · Google Trends `#4fc3f7` · Steam `#81c784`
- Y-axis: avg score (0–100) per topic-source combination
- Tooltip: source, topic, query, score, confidence

### Table columns
| Column | Value |
|---|---|
| Query | query string |
| Topic | topic (coloured badge) |
| Source | source icon + name |
| Score | 0–100, colour-coded (≥60 green, ≥35 amber, else red) |
| Confidence | 0.0–1.0 as % bar |
| Sample Size | sample_size |
| Collected | signal_time relative (e.g. "2h ago") |
| Notes | notes truncated |

Data comes from `external-signals` endpoint. If `items` object is empty, show empty state with "No external signals — click Refresh to fetch."

---

## Tab 3 — Auction Intel

### Slicers
- **Urgency** pill filter (radio): All · 🔴 Ending Soon (&lt;1hr) · 🟡 Today · ⬜ Upcoming
- **Sort** dropdown: Time Left ↑ · Price ↑ · Profit ↓ · Score ↓

### Chart
- Horizontal `BarChart` (Recharts, responsive, 200px height)
- X-axis: estimated_profit (£)
- Y-axis: listing title (truncated to 25 chars)
- Bar fill: urgency colour — `#ef4444` ending_soon · `#f59e0b` today · `#374151` upcoming
- Shows top 10 by profit
- Tooltip: title, price, time left, urgency

### Table columns
| Column | Value |
|---|---|
| Listing | title (link to url, opens new tab) |
| CPU / GPU | cpu + gpu |
| Bid | current price |
| Est. Profit | estimated_profit, coloured |
| Score | gem_score /100 |
| Classification | ClassificationBadge component |
| Time Left | countdown formatted (e.g. "22 min", "6 hr", "2 days") |
| Urgency | coloured dot + label |

Left border accent on rows: red for ending_soon, amber for today, grey for upcoming.

---

## Sidebar nav

Add to `PRIMARY_NAV` in `components/sidebar.tsx`:
```ts
{ href: "/demand", icon: TrendingUp, label: "Demand" },
```
Insert after `{ href: "/sources", ... }` (second position).

`TrendingUp` is already imported from lucide-react in that file. Confirm before adding.

---

## File to create

- `pc-flipper/app/demand/page.tsx` — entire page (~400 lines)

## Files to modify

- `pc-flipper/components/sidebar.tsx` — add nav item

---

## Error / loading states

- Each tab shows a spinner while its endpoint loads
- If fetch fails, show inline error banner: "Failed to load [tab name] — [Retry]"
- Empty state per tab if data returns empty arrays

---

## Out of scope

- No backend changes — all endpoints exist
- No drill-down to individual listings from this page
- No date range filter (data is always "current active listings")
- No export / CSV download
