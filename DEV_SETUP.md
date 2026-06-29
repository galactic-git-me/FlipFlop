# FlipFlop Development Setup with Docker

This guide explains how to run FlipFlop in development mode with hot-reload containers that automatically refresh when you change code.

## Quick Start

```bash
./start-dev.sh
```

This will:
1. ✅ Stop any existing dev containers
2. ✅ Build development Docker images
3. ✅ Start all services with auto-reload
4. ✅ Display URLs and useful commands

## Services

### Storefront (Customer App)
- **URL:** http://localhost:13000
- **Hot Reload:** ✅ Enabled (next dev)
- **Auto-restarts on:** .tsx, .ts, .css file changes

### Admin Dashboard
- **URL:** http://localhost:13001
- **Hot Reload:** ✅ Enabled (next dev)
- **Auto-restarts on:** .tsx, .ts, .css file changes

### API (Backend)
- **URL:** http://localhost:18000
- **Hot Reload:** ✅ Enabled (uvicorn --reload)
- **Auto-restarts on:** .py file changes

### Database
- **Type:** PostgreSQL 16
- **Port:** 15432
- **User:** flipper
- **Password:** flipper_secure_password_123
- **Database:** flipflop

### Cache
- **Type:** Redis 7
- **Port:** 16379

## Development Workflow

### 1. Start Development Environment
```bash
./start-dev.sh
```

### 2. Make Code Changes

**Storefront Example:**
```bash
# Edit flipflop-storefront/app/page.tsx
# The browser automatically reloads!
```

**API Example:**
```bash
# Edit flipflop-api/app/routes/quotes.py
# The API automatically restarts and reloads!
```

**Admin Example:**
```bash
# Edit flipflop-admin/components/OrderQueue.tsx
# The admin dashboard automatically reloads!
```

### 3. View Live Logs

```bash
# All services
docker compose -f docker-compose.dev.yml logs -f

# Specific service
docker compose -f docker-compose.dev.yml logs -f api
docker compose -f docker-compose.dev.yml logs -f storefront
docker compose -f docker-compose.dev.yml logs -f admin
```

### 4. Stop Development Environment

```bash
docker compose -f docker-compose.dev.yml down
```

### 5. Clean Everything (Fresh Start)

```bash
docker compose -f docker-compose.dev.yml down -v
```

## Volume Mounts

Each service has volumes mounted for hot-reload:

```yaml
# Backend (FastAPI)
- ./flipflop-api:/app         # Source code
- /app/.venv                   # Exclude virtualenv
- /app/__pycache__             # Exclude cache

# Storefront (Next.js)
- ./flipflop-storefront:/app  # Source code
- /app/node_modules            # Exclude node_modules
- /app/.next                   # Exclude build cache

# Admin (Next.js)
- ./flipflop-admin:/app        # Source code
- /app/node_modules            # Exclude node_modules
- /app/.next                   # Exclude build cache
```

## Troubleshooting

### Service Not Auto-Reloading?

1. **Check logs:**
   ```bash
   docker compose -f docker-compose.dev.yml logs -f api
   ```

2. **Verify volume mount:**
   ```bash
   docker compose -f docker-compose.dev.yml exec api ls -la /app
   ```

3. **Restart service:**
   ```bash
   docker compose -f docker-compose.dev.yml restart api
   ```

### Port Already in Use?

Edit `docker-compose.dev.yml` and change the port mappings:

```yaml
ports:
  - "23000:3000"  # Change 23000 to any available port
```

### Database Connection Error?

Wait 5-10 seconds for PostgreSQL to start, then restart the API:

```bash
docker compose -f docker-compose.dev.yml restart api
```

### npm Dependencies Not Found?

Rebuild the image:

```bash
docker compose -f docker-compose.dev.yml build --no-cache storefront
docker compose -f docker-compose.dev.yml up -d storefront
```

## Development Tips

### 1. Monitor All Logs
```bash
docker compose -f docker-compose.dev.yml logs -f
```

### 2. Restart Specific Service
```bash
docker compose -f docker-compose.dev.yml restart api
```

### 3. Access Database Directly
```bash
docker compose -f docker-compose.dev.yml exec postgres psql -U flipper -d flipflop
```

### 4. Access Redis CLI
```bash
docker compose -f docker-compose.dev.yml exec redis redis-cli
```

### 5. Execute Command in Container
```bash
# Run Python command
docker compose -f docker-compose.dev.yml exec api python -c "import sys; print(sys.version)"

# Run npm command
docker compose -f docker-compose.dev.yml exec storefront npm list
```

## Performance Notes

- **First Load:** 10-15 seconds (dependencies install + build)
- **Hot Reload:** 1-3 seconds (code change to refresh)
- **Memory Usage:** ~2-3 GB total for all services

## Using Andromeda-TS

The development environment uses `andromeda-ts` as the hostname (mapped to localhost via `extra_hosts`). This allows services to communicate internally using this hostname.

If you need to access services from your host machine, use `localhost` instead:
- Storefront: http://localhost:13000
- Admin: http://localhost:13001
- API: http://localhost:18000

## Switching Between Dev and Production

### Start Development
```bash
./start-dev.sh
# OR
docker compose -f docker-compose.dev.yml up -d
```

### Stop Development
```bash
docker compose -f docker-compose.dev.yml down
```

### Start Production
```bash
docker compose -f docker-compose.local.yml up -d
```

### Stop Production
```bash
docker compose -f docker-compose.local.yml down
```

## Debugging

### Enable Verbose Logging
```bash
# Backend
docker compose -f docker-compose.dev.yml logs -f api --tail=100

# View timestamps
docker compose -f docker-compose.dev.yml logs -f --timestamps
```

### Check Container Health
```bash
docker compose -f docker-compose.dev.yml ps
```

### Inspect Container
```bash
docker compose -f docker-compose.dev.yml inspect flipflop-backend-dev
```

## File Structure

```
FlipFlop/
├── docker-compose.dev.yml      # Development compose file
├── docker-compose.local.yml    # Production compose file
├── start-dev.sh                # Dev startup script
├── DEV_SETUP.md               # This file
├── flipflop-api/
│   ├── Dockerfile             # Production Dockerfile
│   ├── Dockerfile.dev         # Development Dockerfile (auto-reload)
│   └── app/
├── flipflop-storefront/
│   ├── Dockerfile             # Production Dockerfile
│   ├── Dockerfile.dev         # Development Dockerfile (hot-reload)
│   └── app/
└── flipflop-admin/
    ├── Dockerfile             # Production Dockerfile
    ├── Dockerfile.dev         # Development Dockerfile (hot-reload)
    └── app/
```

## Next Steps

1. **Start dev environment:** `./start-dev.sh`
2. **Open storefront:** http://localhost:13000
3. **Make a code change** in `flipflop-storefront/app/page.tsx`
4. **Watch it auto-reload** in your browser!

Happy developing! 🚀
