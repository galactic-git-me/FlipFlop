# FlipFlop Platform - Start All Servers

This launcher starts only the local FlipFlop development servers on
`prometheus-ts`. It never deploys, starts, or modifies production on
`andromeda-ts`.

## Servers

| Server | Type | Port | Technology |
|--------|------|------|------------|
| Backend | API | 4311 | FastAPI (Python) |
| Admin | Web | 4312 | Next.js (Node.js) |
| Frontend | Web | 4313 | Next.js (Node.js) |
| Gem Radar standalone (optional) | API/worker | 18000 | FastAPI (Python) |

## Quick Start

### Windows (PowerShell)
```powershell
# From project root
.\scripts\start-all-servers.ps1

# Or skip specific servers
.\scripts\start-all-servers.ps1 -NoBackend
.\scripts\start-all-servers.ps1 -NoAdmin
.\scripts\start-all-servers.ps1 -NoFrontend

# Optional: also start the standalone DEV Gem Radar worker
.\scripts\start-all-servers.ps1 -GemRadarStandalone

# Optional: rebuild the unpacked DEV browser extension first
.\scripts\start-all-servers.ps1 -BuildExtension

# Validate prerequisites without starting or stopping anything
.\scripts\start-all-servers.ps1 -CheckOnly
```

### Windows (Command Prompt)
```batch
# From project root
scripts\start-all-servers.bat
```

### macOS/Linux (Bash)
```bash
# From project root
chmod +x scripts/start-all-servers.sh
./scripts/start-all-servers.sh

# Or with verbose output
./scripts/start-all-servers.sh -v

# Or skip specific servers
./scripts/start-all-servers.sh --no-backend
./scripts/start-all-servers.sh --no-admin
./scripts/start-all-servers.sh --no-frontend
```

## Access URLs

Once all servers are running, access them at:

- **Backend API**: http://localhost:4311
- **Admin Dashboard**: http://localhost:4312
- **Frontend Shop**: http://localhost:4313

## Features

✅ Starts all three development servers in parallel
✅ Displays status and port information  
✅ Shows colorized output for easy identification  
✅ Supports selective server startup  
✅ Uses hot reload for API and frontend development
✅ Routes DEV AI requests through Ollama priority port 11435

## Logs

### Windows (PowerShell)
Logs are written to the repository's `logs` directory with a unique timestamp
and launcher PID in each filename. This avoids collisions with logs still held
open by an abandoned DEV process. The launcher remains in the foreground so
`Ctrl+C` can stop every development process it started.

### macOS/Linux (Bash)
Logs are written to:
- `/tmp/flipflop-backend.log`
- `/tmp/flipflop-admin.log`
- `/tmp/flipflop-frontend.log`

View logs while running:
```bash
tail -f /tmp/flipflop-backend.log
tail -f /tmp/flipflop-admin.log
tail -f /tmp/flipflop-frontend.log
```

## Stopping Servers

### Windows
Press `Ctrl+C` in the PowerShell or Command Prompt window.

### macOS/Linux
Press `Ctrl+C` in the terminal. The script will clean up processes and PIDs file.

## Requirements

### Backend
- Python 3.x
- Virtual environment activated (`.venv` or `.venv_bsc`)
- Dependencies installed (`pip install -r requirements-dev.txt`)

### Admin & Frontend
- Node.js 18+
- npm or yarn installed
- Dependencies installed (`npm install`)

## Troubleshooting

### "Path not found" error
Ensure you're running the script from the project root or adjust the working directory.

### "Port already in use"
If a port is already in use:
1. Find the process: `lsof -i :4311` (macOS/Linux) or `netstat -ano | findstr :4311` (Windows)
2. Kill the process: `kill <PID>` (macOS/Linux) or `taskkill /PID <PID> /F` (Windows)
3. Run the script again

### Backend fails to start
Check that Python virtual environment is set up:
```bash
cd flipflop-api
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
```

### Node.js servers fail to start
Check that npm dependencies are installed:
```bash
cd flipflop-admin
npm install

cd ../FlipFlop.shop
npm install
```

## Environment Variables

The scripts automatically set required environment variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:4311` |
| `BACKEND_URL` | `http://127.0.0.1:4311` |
| `FLIPFLOP_RUNTIME_ENV` | `development` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11435` |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` (default) |
| `EBAY_ENVIRONMENT` | `production` (read/sourcing) |
| `EBAY_LISTING_ENVIRONMENT` | `sandbox` (writes/listing) |

All backend LLM workflows use `app/services/model_selection_service.py`.
The default hierarchy is `LLM_PRIMARY_PROVIDER=ollama` with
`LLM_PRIMARY_MODEL=qwen2.5:7b-instruct`, then the configured OpenRouter free
model (`LLM_SECONDARY_PROVIDER=openrouter-free` and
`LLM_SECONDARY_MODEL=google/gemma-4-31b-it:free`), then
`LLM_TERTIARY_PROVIDER=openrouter` with `LLM_TERTIARY_MODEL=auto:cheapest`.
OpenRouter tiers require `OPENROUTER_API_KEY`. Set those `LLM_*` variables in
the API runtime environment to change the provider/model order. Keep
`OLLAMA_BASE_URL` environment-specific: development uses the local gateway on
port `11435` (second priority); production worker traffic uses the
`ollama-tunnel` service on container port `11434`, which forwards to the
production-priority listener on Prometheus port `11436`. Other local apps use
Prometheus port `11434` (third priority). Vision requests skip text-only local models and select a
vision-capable configured/cloud tier.

The launcher sets these explicitly so a stale shell environment cannot point
development at production accidentally.

## Advanced Usage

### Running only specific servers

**Backend only:**
```powershell
# Windows
.\scripts\start-all-servers.ps1 -NoAdmin -NoFrontend

# macOS/Linux
./scripts/start-all-servers.sh --no-admin --no-frontend
```

**Admin only:**
```powershell
# Windows
.\scripts\start-all-servers.ps1 -NoBackend -NoFrontend
```

**Frontend only:**
```powershell
# Windows
.\scripts\start-all-servers.ps1 -NoBackend -NoAdmin
```

### Manual Server Startup

If you prefer to start servers individually:

#### Backend (FastAPI)
```bash
cd flipflop-api
python run_dev.py --host 0.0.0.0 --port 4311
```

#### Admin (Next.js)
```bash
cd flipflop-admin
NEXT_PUBLIC_API_URL=http://localhost:4311 npm run dev -- -p 4312 -H 0.0.0.0
```

#### Frontend (Next.js)
```bash
cd ../FlipFlop.shop
BACKEND_URL=http://localhost:4311 NEXT_PUBLIC_API_URL=http://localhost:4311 npm run dev -- -p 4313 -H 0.0.0.0
```

## Notes

- The scripts automatically configure the correct API URLs for each frontend
- All servers listen on `0.0.0.0` to allow external connections
- The PowerShell script monitors processes and reports if any exit unexpectedly
- Environment variables are set per-process and don't affect the system globally
