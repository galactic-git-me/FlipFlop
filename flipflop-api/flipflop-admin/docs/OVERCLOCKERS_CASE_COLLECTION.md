# Overclockers Case Collection & Curation Guide

## Overview

This guide walks you through collecting all Overclockers cases and curating the best 10 for your PC Flipper showcase.

**Architecture:**
- **Browser collection**: Your logged-in Overclockers session (bypasses Cloudflare blocks)
- **Backend submission**: `POST /api/cases/bulk-import` (upserts into Part table)
- **Admin curation**: `GET /api/cases/curated` + `POST /api/cases/mark-curated`

---

## Step 1: Collect Cases from Overclockers Browser

### Option A: Manual Collection (Recommended)

1. **Login to Overclockers** (required to bypass geo-blocks)
   - Open https://www.overclockers.co.uk/ in your browser
   - Sign in with your account

2. **Navigate to PC Cases**
   - Go to https://www.overclockers.co.uk/search?sSearch=PC+case
   - You should see multiple pages of results

3. **Run the Collector Script**
   - Press **F12** to open Developer Tools (Console tab)
   - Open `flipflop-admin/app/cases-collector.ts` and copy the entire script
   - Paste into the browser console and press Enter
   - You should see: `✅ Case collector loaded. Run: collectAndSubmitCases() to start.`

4. **Start Collection**
   - Type `collectAndSubmitCases()` in the console and press Enter
   - The script will:
     - Scrape all visible cases from the current page
     - Navigate to the next page automatically
     - Continue until all pages are collected
     - Submit the batch to your backend API

5. **Monitor Progress**
   - Watch the console for log messages:
     ```
     🔄 Starting case collection from Overclockers...
     Collected 24 cases from current page, total: 24
     Moving to next page...
     Collected 18 cases from current page, total: 42
     ...
     📤 Submitting to backend...
     ✅ Cases submitted successfully: {inserted: 42, updated: 0, skipped: 0}
     ```

### Option B: Batch Collection from Search Results

If the automated pagination doesn't work:
1. Open each search results page manually
2. For each page, open the console and run:
   ```javascript
   const cases = await extractCasesFromPage()
   console.log(JSON.stringify(cases, null, 2))
   ```
3. Copy all cases into a JSON file
4. Manually POST to `/api/cases/bulk-import` with all collected cases

---

## Step 2: Backend API Endpoints

### POST `/api/cases/bulk-import`

Submit a batch of collected cases.

**Request:**
```json
{
  "cases": [
    {
      "name": "NZXT H510 Mid Tower Case",
      "price": 79.99,
      "source_site": "Overclockers",
      "source_url": "https://www.overclockers.co.uk/nzxt-h510",
      "image_url": "https://...",
      "theme": "Overclockers Collection",
      "supplier": "Overclockers",
      "rating": null,
      "in_stock": true,
      "specs": "ATX Mid Tower"
    }
    // ... more cases
  ]
}
```

**Response:**
```json
{
  "inserted": 42,
  "updated": 0,
  "skipped": 2,
  "errors": 0
}
```

### GET `/api/cases/curated?source=Overclockers&limit=100`

Retrieve all imported cases for review and curation.

**Response:**
```json
[
  {
    "id": 123,
    "name": "NZXT H510 Mid Tower Case",
    "price": 79.99,
    "source_site": "Overclockers",
    "source_url": "https://www.overclockers.co.uk/nzxt-h510",
    "image_url": "https://...",
    "theme": "Overclockers Collection",
    "supplier": "Overclockers",
    "rating": null,
    "specs": "ATX Mid Tower",
    "created_at": "2026-08-20T12:00:00",
    "last_price_update": "2026-08-20T12:00:00"
  }
  // ... more cases, sorted by price ascending
]
```

### POST `/api/cases/mark-curated`

Mark 10 specific cases as the curated selection.

**Request:**
```json
{
  "case_ids": [123, 124, 125, 126, 127, 128, 129, 130, 131, 132]
}
```

**Response:**
```json
{
  "success": true,
  "selected_count": 10
}
```

---

## Step 3: Curate the 10 Best Cases

### Admin Workflow

1. **Review all imported cases**
   ```bash
   curl http://localhost:18000/api/cases/curated?source=Overclockers
   ```

2. **Filter by theme/price**
   - Group cases by theme (e.g., "Airflow RGB", "White Gaming")
   - Sort by price (cheapest first for budget options)
   - Look for variety: different sizes (ITX, ATX, E-ATX), colors, build styles

3. **Select top 10**
   - Choose cases that offer diverse aesthetics
   - Prefer cases in stock
   - Aim for £50–200 price range
   - Pick a mix of themes for versatility in builds

4. **Mark as curated**
   ```bash
   curl -X POST http://localhost:18000/api/cases/mark-curated \
     -H "Content-Type: application/json" \
     -d '{"case_ids": [123, 124, 125, 126, 127, 128, 129, 130, 131, 132]}'
   ```

---

## Troubleshooting

### Script doesn't run
- Check that you're logged into Overclockers (sign-in status required)
- Verify the URL is exactly: `https://www.overclockers.co.uk/search?sSearch=PC+case`
- Check browser console for errors (F12 → Console tab)

### Pagination fails
- Overclockers may have changed their pagination markup
- Manually collect each page and build a JSON file
- Submit via curl: `curl -X POST http://localhost:18000/api/cases/bulk-import -d @cases.json`

### Backend 502 error
- Verify the backend is running: `pm2 status` or `python -m uvicorn app.main:app`
- Check that Part table exists: `sqlite3 flipflop.db ".tables"` should show `part`

### Cases not saving
- Check database permissions: `ls -la flipflop.db`
- Review backend logs: `pm2 logs gemradar-api-18000` or server output
- Verify schema: `sqlite3 flipflop.db ".schema part"` should show `category` column

---

## Testing Locally

### 1. Start the backend
```bash
cd flipflop-api
pm2 start gemradar-api-18000
```

### 2. Test the import endpoint
```bash
curl -X POST http://localhost:18000/api/cases/bulk-import \
  -H "Content-Type: application/json" \
  -d '{
    "cases": [
      {
        "name": "Test Case 1",
        "price": 79.99,
        "source_site": "Overclockers",
        "source_url": "https://example.com/case1",
        "image_url": null,
        "theme": "Test",
        "supplier": "Overclockers",
        "rating": null,
        "in_stock": true,
        "specs": "ATX"
      }
    ]
  }'
```

### 3. Retrieve curated cases
```bash
curl http://localhost:18000/api/cases/curated?source=Overclockers&limit=10
```

---

## Future Enhancements

- [ ] Add rating/review field to Part model (store supplier ratings)
- [ ] Build admin UI page to visualize and select 10 cases with thumbnails
- [ ] Auto-generate PC build recommendations from selected cases
- [ ] Track which cases are "featured" vs. "available"
- [ ] Sync selected cases to public showcase API
- [ ] Add case filters: form factor (ITX/ATX/E-ATX), color, RGB support

---

## Notes

- **Overclockers geo-blocks**: Server-side requests fail due to Cloudflare. Browser-based collection is the reliable workaround.
- **Database structure**: Cases are stored in the existing `Part` table with `category='case'`, so they integrate seamlessly with the inventory system.
- **Bulk import is idempotent**: Submitting the same case twice will update the price but not create duplicates (keyed by `source_url`).
