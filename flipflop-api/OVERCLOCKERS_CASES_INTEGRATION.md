# Overclockers Case Integration — Complete

## What Changed

I **added Overclockers to the existing cases swarm** using the **direct httpx method** (same pattern as eBay).

Overclockers has no API, so the scraper uses **httpx + BeautifulSoup** — the same proven approach eBay uses. This is the primary/only method, not a fallback.

The cases swarm was already scraping 9 sources (eBay, Amazon, Temu, AliExpress, Etsy, Gumtree, Vinted, BargainHardware, CherryTree, Alibaba). Now it includes **Overclockers as source #10**.

### Key Additions

**Files**: 
- `flipflop-api/app/services/scraper.py` — new `scrape_overclockers_cases()` function
- `flipflop-api/app/swarms/cases.py` — `_scrape_overclockers()` calls the scraper

1. **New scraper function**: `scrape_overclockers_cases()`
   - Uses **httpx** with headers (no API, no Playwright)
   - Mimics eBay pattern exactly
   - Scrapes entire PC cases section (not search terms)
   - Parses HTML with BeautifulSoup
   - Price range: £10–500
   - Returns list of `RawListing` objects

2. **Updated cases swarm**: `_scrape_overclockers()`
   - Calls `scrape_overclockers_cases()` from scraper service
   - Converts results to `RawCase` objects
   - Auto-upserts into `Part` table

### How It Works

The existing cases swarm runs daily and now:

1. Calls `scrape_overclockers_cases()` (httpx-based)
2. Makes HTTP request to Overclockers PC cases page
3. Parses HTML with BeautifulSoup (same as eBay)
4. Extracts product links, prices, images
5. Upserts into `Part` table (category = "case")
6. Records price history automatically

### Configuration

Cases are already configured to search Overclockers through the existing `SourceSearchTerm` table:

```sql
SELECT * FROM source_search_term 
WHERE scope = 'cases' AND enabled = 1 AND source_names LIKE '%Overclockers%';
```

Add terms via the admin API:
```bash
POST /api/source-search-terms
{
  "scope": "cases",
  "term": "gaming pc case rgb",
  "group_name": "RGB Cases",
  "source_names": ["Overclockers", "Amazon", "eBay"],
  "enabled": true
}
```

### Testing

Trigger a manual case swarm run:

```bash
# In Python
from app.swarms.cases import run_cases_swarm
import asyncio

result = asyncio.run(run_cases_swarm(mode="main"))
print(result)  # {'found': X, 'upserted': Y, 'errors': Z}
```

Or via the admin endpoint:

```bash
curl -X POST http://localhost:18000/api/admin/swarms/run?name=cases
```

### Results

When the swarm runs:

- **New cases** are inserted into `Part` table with category='case', source_site='Overclockers'
- **Existing URLs** are updated with new prices (idempotent upsert)
- **Price history** is recorded automatically
- Cases are integrated with the existing inventory system immediately

### Database Query

See all Overclockers cases:

```sql
SELECT id, name, price, theme, created_at, last_price_update
FROM part
WHERE category = 'case' AND source_site = 'Overclockers'
ORDER BY price ASC
LIMIT 20;
```

---

## Why This Approach

✅ **Reuses existing infrastructure** — no separate intake workflow needed
✅ **Fully automated** — runs on the daily swarm schedule
✅ **Integrated pricing** — price history tracked automatically
✅ **Deduplication** — handles updates gracefully (same URL = update, not duplicate)
✅ **Multi-source** — cases come from all 10 sources uniformly
✅ **Zero user friction** — no manual collection or submission required

---

## Next Steps

1. **Run the swarm** to collect Overclockers cases
2. **Review results** via the existing catalogue APIs
3. **Select top 10** for your showcase (filter by price, theme, rating)
4. **Use in PC build recommendations** — cases integrate with the flipper workflow

---

## Previous Work (Archived)

The bulk-import endpoint (`POST /api/cases/bulk-import`) was created as a fallback if Overclockers couldn't be scraped directly. Now that the swarm handles it, the bulk-import is available only if you need to:
- Manually import cases from other sources
- Supplement with pre-collected data
- Use the browser-side collector from FlipFlopXtension

But it's no longer needed for Overclockers specifically.
