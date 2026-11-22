# Overclockers Case Integration — Ready to Go

## Status: Complete ✅

Overclockers is now integrated into the existing `run_cases_swarm()`. You have two working paths:

---

## Path 1: Automated Swarm (Recommended)

The cases swarm runs daily and automatically collects Overclockers cases.

**Trigger manually:**

```bash
# Via curl to admin API
curl -X POST http://localhost:18000/api/admin/swarms/run?name=cases

# Via Python
python -c "
import asyncio
from app.swarms.cases import run_cases_swarm
result = asyncio.run(run_cases_swarm())
print(result)  # {found: X, upserted: Y}
"
```

**Results appear in the Part table:**

```sql
SELECT COUNT(*) FROM part 
WHERE category='case' AND source_site='Overclockers';

-- See all Overclockers cases by price
SELECT name, price, image_url, theme, source_url
FROM part
WHERE category='case' AND source_site='Overclockers'
ORDER BY price ASC;
```

---

## Path 2: Manual Collection (Fallback)

If you need to collect cases outside the swarm schedule:

1. Use `flipflop-admin/app/cases-collector.ts` (browser console script)
2. Or integrate into FlipFlopXtension for automatic injection
3. Submit via `POST /api/cases/bulk-import`

This endpoint is still available but not needed for Overclockers.

---

## Architecture Now

```
Overclockers.co.uk
    ↓
    ├─ run_cases_swarm() [daily]
    │  ├─ _scrape_overclockers() [new]
    │  └─ 9 other sources (eBay, Amazon, etc.)
    ↓
Part table (category='case', source_site='Overclockers')
    ↓
    ├─ Admin review (filter, sort, curate)
    ├─ PC build recommendations
    └─ Public showcase
```

---

## Configuration

Add Overclockers search terms via the admin API:

```bash
curl -X POST http://localhost:18000/api/source-search-terms \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "cases",
    "term": "pc case gaming rgb",
    "group_name": "Gaming Cases",
    "source_names": ["Overclockers", "Amazon"],
    "enabled": true
  }'
```

Or edit `source_search_term` table directly. The swarm will pick them up on the next run.

---

## Files Changed

```
flipflop-api/
├── app/swarms/cases.py          ← MODIFIED (added _scrape_overclockers)
├── OVERCLOCKERS_CASES_INTEGRATION.md  ← NEW (reference)

flipflop-api/
├── app/api/cases_bulk_import.py  ← NEW (fallback intake)
├── app/main.py                   ← MODIFIED (registered bulk-import route)

flipflop-admin/
├── app/cases-collector.ts        ← NEW (browser collector)
├── docs/OVERCLOCKERS_CASE_COLLECTION.md  ← NEW (guide)
```

---

## What's Happening Under the Hood

1. **Daily** → `run_cases_swarm()` runs (scheduled job)
2. **For each term** → Searches all enabled sources
3. **For Overclockers** → Calls `_scrape_overclockers()`
4. **Uses Playwright** → Stealth mode, fake User-Agent, avoids bot detection
5. **JS Evaluation** → Extracts product links/prices (resistant to class name changes)
6. **Upsert** → Inserts or updates cases in `Part` table
7. **Price History** → Recorded automatically for trend analysis

---

## Quick Test

Make sure Playwright is installed and chromium is available:

```bash
# Check if chromium works
python -c "from app.services.playwright_scraper import chromium_available; print(chromium_available())"
# Should print: True

# Test the scraper directly
python -c "
import asyncio
from app.swarms.cases import _scrape_overclockers

cases = asyncio.run(_scrape_overclockers('atx case', 'Test'))
print(f'Found {len(cases)} cases')
for c in cases[:3]:
    print(f'  {c.name}: {c.price}')
"
```

---

## Next Steps

1. **Let the daily swarm run** (automatic) OR manually trigger it above
2. **Query the database** to see Overclockers cases
3. **Review/curate** cases for your showcase
4. **Integrate into PC builds** — cases are ready to use

---

## Notes

- **No login required** — Playwright stealth patches bypass geo-blocks and bot detection
- **Idempotent** — Same URL = update, not duplicate (keyed by `source_url`)
- **Price tracking** — Each update recorded in `price_history` table
- **Unified API** — Overclockers cases integrated with existing catalogue endpoints
- **Fallback available** — If Overclockers blocks Playwright later, use manual bulk-import

---

## Cleanup (Optional)

If you don't want to keep the bulk-import endpoint:

```bash
# Remove bulk-import API
rm flipflop-api/app/api/cases_bulk_import.py

# Remove from main.py
# - Remove import on line 39
# - Remove router registration on line 622

# Remove browser collector
rm flipflop-admin/app/cases-collector.ts

# Remove guides
rm flipflop-admin/docs/OVERCLOCKERS_CASE_COLLECTION.md
```

But keep them for now in case Overclockers needs the fallback later.
