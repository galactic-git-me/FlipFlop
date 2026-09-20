#!/usr/bin/env bash
# Cloud Agent environment install for FlipFlop.
#
# Prepares the two canonical dev services described in CLAUDE.md:
#   * gemradar-api-18000  — standalone Gem Radar FastAPI (Postgres-backed)
#   * flipflop-admin-3002 — Next.js admin dashboard
#
# Idempotent: safe to run repeatedly and against a warm snapshot. Durable state
# (installed packages, virtualenv, node_modules, the dev database + schema) is
# prepared here so per-boot startup in start.sh stays fast.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> [1/6] Ensuring system packages (postgres, redis, build tools)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
  postgresql postgresql-contrib redis-server \
  python3-venv python3-dev build-essential libpq-dev curl

echo "==> [2/6] Starting Postgres + Redis so the dev database can be prepared"
sudo pg_ctlcluster 16 main start 2>/dev/null || true
sudo service redis-server start 2>/dev/null || true
for _ in $(seq 1 30); do
  pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1 && break
  sleep 1
done

echo "==> [3/6] Ensuring the flipper role and pcflipper database exist"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='flipper'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE flipper LOGIN PASSWORD 'flipper';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='pcflipper'" | grep -q 1 \
  || sudo -u postgres createdb -O flipper pcflipper
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE pcflipper TO flipper;" >/dev/null

echo "==> [4/6] Installing Python API dependencies"
cd "$REPO_ROOT/flipflop-api"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

if [ ! -f .env.local ]; then
  echo "    creating flipflop-api/.env.local (dev defaults)"
  cat > .env.local <<'EOF'
# Local development env for the standalone Gem Radar API (Cloud Agent).
DATABASE_URL=postgresql+asyncpg://flipper:flipper@127.0.0.1:5432/pcflipper
SYNC_DATABASE_URL=postgresql://flipper:flipper@127.0.0.1:5432/pcflipper
REDIS_URL=redis://127.0.0.1:6379/0
# Ollama is disabled in dev; OLLAMA_MODEL is a required settings field so it
# must still be present.
OLLAMA_MODEL=disabled
# Serve the API without ingestion/scraper/scheduler workers so it is safe to
# leave running continuously with no external scraping side effects.
WEB_ONLY=true
APP_ENV=dev
EOF
fi

echo "==> [5/6] Initialising the database schema"
PYTHONPATH="$REPO_ROOT/flipflop-api" ./.venv/bin/python "$REPO_ROOT/.cursor/schema_init.py"

echo "==> [6/6] Installing admin dashboard dependencies"
cd "$REPO_ROOT/flipflop-admin"
if [ ! -f .env.local ]; then
  echo "    creating flipflop-admin/.env.local (dev defaults)"
  cat > .env.local <<'EOF'
# Local development env for the FlipFlop admin dashboard (Cloud Agent).
# Point the dashboard proxy at the standalone Gem Radar API on port 18000.
GEMRADAR_URL=http://localhost:18000
BACKEND_URL=http://localhost:18000
# Shared HS256 secret used to verify the admin_session cookie (dev-only).
ADMIN_JWT_SECRET=dev-admin-jwt-secret-change-in-production
EOF
fi
npm install

echo "==> Install complete."
