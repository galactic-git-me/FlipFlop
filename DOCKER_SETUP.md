# Docker Compose Setup - FlipFlop Platform

This Docker Compose configuration replaces the PowerShell startup script (`scripts/start-all-servers.ps1`) with containerized services that auto-restart on failure.

## Services Included

| Service | Port | Description |
|---------|------|-------------|
| postgres | 5432 | PostgreSQL database |
| ollama | 11434 | Qwen2:7b GPU-accelerated LLM |
| backend | 4311 | FastAPI backend |
| gemradar-api | 18000 | Gem Radar data pipeline |
| admin | 4312 | Next.js admin dashboard |
| frontend | 4313 | Next.js frontend shop |

## Quick Start

```powershell
cd C:\Users\mclar\CODING\FlipFlop
docker-compose build
docker-compose up -d
docker-compose ps
```

## Key Features

- Auto-restart on failure (restart: always)
- Health checks for all services
- Global CPK semaphore (4 concurrent)
- OLLAMA_NUM_PARALLEL=4 (GPU optimal)
- Persistent database storage

## Management Commands

```powershell
# Use the helper script
./start-docker.ps1 up
./start-docker.ps1 logs
./start-docker.ps1 down

# Or use docker-compose directly
docker-compose logs -f
docker-compose restart backend
```

See full documentation in this file for troubleshooting and advanced usage.
