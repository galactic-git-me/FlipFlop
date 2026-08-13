# Gem Radar Submission Queue System

## Overview

The submission queue prevents data loss if the backend goes down. Extension submissions are stored in the database and processed asynchronously by a background worker.

## Flow

```
Extension
    ↓
POST /api/gem-radar/scans-queued  (returns 202 Accepted immediately)
    ↓
SubmissionQueue table (persisted to PostgreSQL)
    ↓
Background Worker (_submission_queue_processor)
    ↓
Processing Pipeline
    ↓
GemRadarScoredListing table
```

## Endpoints

### Original (Synchronous)
**POST /api/gem-radar/scans**
- Returns full `ScanSubmitResponse` with results
- Processes immediately (can timeout on large scans)
- Data is lost if backend crashes during processing

### New (Asynchronous/Queued)
**POST /api/gem-radar/scans-queued**
- Returns 202 Accepted immediately with:
  ```json
  {
    "searchRunId": "...",
    "submissionId": 123,
    "status": "queued",
    "message": "Submission queued for processing"
  }
  ```
- Submission stored in `submission_queue` table
- Background worker processes asynchronously
- Data survives backend restarts

## Request Format (Same for Both)

```json
{
  "searchRunId": "unique-id",
  "searchId": "category-id",
  "query": "AMD CPU",
  "sourceUrl": "https://...",
  "maxCandidatesForDeepResearch": 50,
  "listings": [
    {
      "listingId": "...",
      "url": "...",
      "title": "...",
      ...
    }
  ]
}
```

## Extension Changes

Update the extension to submit to `/scans-queued` instead of `/scans`:

```typescript
// OLD
const response = await fetch('http://127.0.0.1:18000/api/gem-radar/scans', {
  method: 'POST',
  body: JSON.stringify(payload),
})

// NEW
const response = await fetch('http://127.0.0.1:18000/api/gem-radar/scans-queued', {
  method: 'POST',
  body: JSON.stringify(payload),
})
```

The queue endpoint returns 202 Accepted (no results), so the extension should:
1. Show "Submission queued" message to user
2. Not wait for results
3. Retry submitting if network fails (same retry logic as before)

## Monitoring Queue Status

**GET /api/gem-radar/queue-stats** (future endpoint)

Currently visible in logs:
- Pending count
- Processing count
- Completed count
- Failed count (with error messages)

```bash
pm2 logs gemradar-api-18000 | grep queue_processor
```

## Retry Policy

Submissions are retried up to 5 times if processing fails:
- Attempt 1: Immediate
- Attempt 2+: Exponential backoff (automatic retry on next worker cycle)
- After 5 failures: Marked as "failed" in database

Failed submissions can be manually reviewed in the `submission_queue` table.

## Database Schema

```sql
submission_queue
├── id (pk)
├── status ('pending', 'processing', 'completed', 'failed')
├── search_run_id
├── search_id
├── query
├── source_url
├── listings_json (JSON array)
├── retry_count (0-5)
├── last_error (text, nullable)
├── first_attempt_at
├── last_attempt_at
├── completed_at (nullable)
├── created_at (auto)
├── updated_at (auto)
```

## Migration

Run the migration to create the `submission_queue` table:

```bash
cd flipflop-api
python -m alembic upgrade head
```

Or manually:

```sql
CREATE TABLE submission_queue (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50) DEFAULT 'pending',
    search_run_id VARCHAR(255) NOT NULL,
    search_id VARCHAR(255) NOT NULL,
    query VARCHAR(500) NOT NULL,
    source_url VARCHAR(1000) NOT NULL,
    max_candidates_for_deep_research INTEGER DEFAULT 50,
    listings_json JSONB NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    first_attempt_at TIMESTAMP DEFAULT NOW(),
    last_attempt_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_submission_queue_status ON submission_queue(status);
CREATE INDEX idx_submission_queue_created_at ON submission_queue(created_at DESC);
```

## Benefits

✅ **Zero data loss** if backend restarts during processing
✅ **Immediate response** (202 Accepted)
✅ **Automatic retries** for transient failures
✅ **Scalable** — multiple submissions can be in queue
✅ **Observable** — queue stats and error tracking in database
✅ **Backward compatible** — `/scans` endpoint still works
