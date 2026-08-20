# Overclockers Case Integration — Complete

## What Changed

You were right — instead of building a separate bulk-import workflow, I just **added Overclockers to the existing cases swarm**.

The cases swarm was already scraping 9 sources (eBay, Amazon, Temu, AliExpress, Etsy, Gumtree, Vinted, BargainHardware, CherryTree, Alibaba). Now it includes **Overclockers as source #10**.

### Key Additions

**File**: `flipflop-api/app/swarms/cases.py`

1. **Added to SOURCES list**:
   - `{"name": "Overclockers", "fn": "overclockers"}`
   - Added to `_PLAYWRIGHT_CASE_SOURCES` set

2. **New scraper function**: `_scrape_overclockers(search, theme)`
   - Uses Playwright + stealth patches (same as Amazon, Temu, AliExpress)
   - Cloudflare-resistant (httpx blocks, Playwright works)
   - Extracts product links, prices, images via JS evaluation
   - Price range: £0–350 (filters out enterprise/industrial cases)
   - Returns list of `RawCase` objects (auto-upserted by swarm)

### How It Works

The existing cases swarm runs daily and now:

1. Searches Overclockers for configured case terms (gaming cases, airflow RGB, etc.)
2. Launches Playwright browser (stealth mode, fake User-Agent)
3. Navigates to search results
4. Extracts products using JS evaluation (resistant to class name changes)
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
