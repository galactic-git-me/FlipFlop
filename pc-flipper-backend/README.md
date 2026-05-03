# PC Flip Profit Maximizer — Backend

FastAPI + PostgreSQL + APScheduler backend for the PC flipping intelligence platform.

## Quick Start

### Option A — Docker (recommended)

```bash
cp .env.example .env
# Edit .env to add ANTHROPIC_API_KEY etc.
docker-compose up -d
```

API available at `http://localhost:8000`  
Docs at `http://localhost:8000/docs`

### Option B — Local Python

```bash
# Requires PostgreSQL + Redis running locally
cp .env.example .env
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

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

Full interactive docs: `http://localhost:8000/docs`

## Swarms

| Swarm | Schedule | What it does |
|-------|----------|--------------|
| `flip_opportunities` | Every 60 min | Scrapes sources, classifies, scores listings |
| `upgrade_parts` | Every 24 hr | Updates used prices for GPU/RAM/SSD/PSU |

Trigger manually via API: `POST /api/swarms/flip_opportunities/trigger`
