# PC Flip Profit Maximizer — Backend

FastAPI + PostgreSQL + APScheduler backend for the PC flipping intelligence platform.

## Quick Start

### Option A — Docker (recommended)

```bash
cp .env.example .env
# Edit .env to add ANTHROPIC_API_KEY etc.
docker-compose up -d
```

API available at `http://localhost:4311`  
Docs at `http://localhost:4311/docs`

### API-image Getting Ready sources

The API-only Docker build context includes packaged copies of the reviewed Getting Ready prompt, dispatch checklist, Rainmeter skin, customer-support guide, and customer-safe Software Playbook section. The repository-level templates/docs are canonical. After changing one of those sources, sync the API copies from the repository root before building or deploying:

```powershell
.\scripts\sync-api-package-sources.ps1
```

To check for drift without changing files:

```powershell
.\scripts\sync-api-package-sources.ps1 -Check
```

### Option B — Local Python

```bash
# Requires PostgreSQL + Redis running locally
cp .env.example .env
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
python run_dev.py           # defaults to port 4311; restarts the API when Python files change
```

The Windows launcher watches `app/` and restarts the API process after Python
source changes. It keeps Uvicorn's built-in reload disabled so the API retains
the Proactor event loop required by Playwright.

Before starting normal DEV mode, apply database migrations. `create_all`
does not add columns to existing tables. Scan schema checks run before worker
startup, submission acceptance, and queue claims; incompatible work stays
pending instead of exhausting retries. `WEB_ONLY=true` rejects scan submissions
with HTTP 503 because sourcing workers are disabled.

To recover the October image/provenance schema failures after schema repair:

```powershell
python scripts/recover_scan_schema_failures.py         # preview
python scripts/recover_scan_schema_failures.py --apply # audited requeue
```

The recovery retains payloads and previous errors and saves an audit in the
workspace `logs/` directory. It targets only the two diagnosed missing-column
errors. On 14 October, `alembic upgrade head` was blocked by the pre-existing
`curated_promotions` table in an older migration branch. The two additive media
and provenance migrations were applied directly; migration history was not
stamped. The branch has now been reconciled: the merge lists only independent
heads, and compatible pre-existing DDL was adopted using the explicit command
below. DEV is at `20261013_0002`; normal upgrades work again.

```powershell
python -m alembic -x reconcile_existing=true upgrade head
python -m alembic current
python -m alembic upgrade head
```

Use reconciliation only for reviewed schema drift. It validates existing
column types, nullability, primary/unique/foreign keys and index definitions;
incompatible definitions stop the transaction rather than being stamped.

Top component cards use active lifecycle state rather than discarding scores
after 24 hours; stored active candidates remain visible during a failed sweep.

## AI Setup

Hermes uses a fallback chain:

1. **Ollama (local, free)** — install from https://ollama.com then:
   ```
   ollama pull gemma2:2b
   ollama serve
   ```
2. **Claude Haiku** — set `ANTHROPIC_API_KEY` in `.env`
3. **OpenRouter free** — set `OPENROUTER_API_KEY` in `.env`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/listings` | Browse listings with filters |
| GET | `/api/listings/stats` | Dashboard stats |
| POST | `/api/flips` | Start a flip |
| PATCH | `/api/flips/{id}` | Update flip stage/upgrades |
| GET | `/api/parts` | Parts pricing |
| GET/PUT | `/api/config/search` | Search config |
| POST | `/api/chat` | Chat with Hermes |
| POST | `/api/swarms/{id}/trigger` | Manually trigger a swarm |

Full interactive docs: `http://localhost:4311/docs`

## Swarms

| Swarm | Schedule | What it does |
|-------|----------|--------------|
| `flip_opportunities` | Every 60 min | Scrapes sources, classifies, scores listings |
| `upgrade_parts` | Every 24 hr | Updates used prices for GPU/RAM/SSD/PSU |

Trigger manually via API: `POST /api/swarms/flip_opportunities/trigger`

## Compliant Market Ingestion

This backend includes a compliant ingestion job that consumes permitted JSON/CSV feeds and normalizes them into:

- `source_runs`
- `listings_raw`
- `listings_normalized`

Setup:

```bash
cp config/compliant_sources.example.json config/compliant_sources.json
# Edit source names and file paths to approved feeds
```

Environment variables:

- `COMPLIANT_INGESTION_MANIFEST_PATH` (default: `config/compliant_sources.json`)
- `COMPLIANT_INGESTION_INTERVAL_HOURS` (default: `6`)

Manual run via swarms API:

- `POST /api/swarms/compliant_market_ingestion/trigger`

### Missing manual-build creation origin (20 October 2026)

`delivery_followup` selects the full `ManualBuild` model. Older installations can lack `manual_builds.creation_method` because its original addition lived only in the disabled broad startup migration. Alembic revision `20261020_0001` adds the required `VARCHAR(20) NOT NULL DEFAULT 'manual'` column without replacing existing build data. It skips an existing compatible column and preserves recorded AI origins.

For the local DEV database only, inspect and narrowly repair this specific drift with:

```powershell
.\.venv\Scripts\python.exe scripts/repair_manual_build_creation_method.py
.\.venv\Scripts\python.exe scripts/repair_manual_build_creation_method.py --apply
```

The default command is read-only and exits nonzero if mapped columns are missing. `--apply` validates matching local async/sync database targets, uses bounded lock/statement timeouts, and verifies existing row data is unchanged in the repair transaction. It applies only the new column migration without stamping Alembic history or running unrelated pending migrations. A later ordinary upgrade skips the already-present compatible column. Roll application code back while retaining this additive column; dropping it loses build-origin history. The check runs the follow-up SELECT only and never invokes the email worker.

The named local `pcflipper` repair preserved 13 builds, left revision `20261015_0004` unchanged and verified the formerly failing query in a fresh connection. Production migration and actual follow-up email delivery were not performed.

### Texture fidelity and source-photo size (20 October 2026)

The four newest owner-generated GLBs were inspected and contained embedded base-colour/PBR maps. The case model's approved references were Amazon `._AC_US40_` 40×40 thumbnails; original copies of those same photo IDs were available at 500×500. Its saved colour atlas was largely grey/low-detail, and the running review viewer reported no loading errors. Low-resolution input is a confirmed pipeline defect; the visual quality of a regenerated model still needs owner review.

Generation now resolves Amazon/eBay thumbnail URLs to original/larger renditions of exactly the approved image IDs, preserving order for geometry and texture guidance. Known public image CDNs are checked before submission; originals below 256 pixels on their longest edge, below 64 on the shortest, unsupported formats or files over 20 MB stop before a paid job. Arbitrary image hosts are not newly fetched by the backend. The submitted original-resolution URLs are recorded in variant generation metadata while `source_image_refs` retains the owner's exact approved selection for the existing model gate. Both single/multi-image requests keep `should_texture` and `enable_pbr` enabled, with 2K texture output. [Meshy image API](https://docs.meshy.ai/en/api/image-to-3d) and [multi-image API](https://docs.meshy.ai/en/api/multi-image-to-3d) define these parameters.

Generated GLBs must contain an embedded colour texture referenced by rendered geometry before storage/publication. This is a structural check, not a substitute for inspecting fidelity. The Playbook photo and model-review panels display larger copies of the same images and offer **Regenerate from approved photos** for unpublished drafts; provider credits apply and every new draft still needs explicit owner approval. Existing drafts and approvals are not overwritten or silently replaced.
