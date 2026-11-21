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
   - You should see: `Case collector loaded. Run: collectAndSubmitCases() to start.`

4. **Start Collection**
   - Type `collectAndSubmitCases()` in the console and press Enter
   - The script will:
     - Scrape all visible cases from the current page
     - Navigate to the next page automatically
     - Continue until all pages are collected
     - Submit the batch to your backend API

5. **Monitor Progress**
   - Watch the console for log messages showing collection progress

### Option B: Use FlipFlopXtension

If you have the extension available, it can inject the case collector directly:
1. Open Overclockers case search page
2. Extension injects collector automatically
3. Cases are submitted to the backend seamlessly

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

### POST `/api/cases/mark-curated`

Mark 10 specific cases as the curated selection.

---

## Step 3: Curate the 10 Best Cases

1. **Review all imported cases**
   ```bash
   curl http://localhost:18000/api/cases/curated?source=Overclockers
   ```

2. **Filter by theme/price** and select top 10

3. **Mark as curated**
   ```bash
   curl -X POST http://localhost:18000/api/cases/mark-curated \
     -H "Content-Type: application/json" \
     -d '{"case_ids": [123, 124, 125, 126, 127, 128, 129, 130, 131, 132]}'
   ```

---

## Testing Locally

### Start the backend
```bash
cd flipflop-api
pm2 start gemradar-api-18000
```

### Test the import endpoint
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
