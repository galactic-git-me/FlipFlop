#!/usr/bin/env bash
# PC Flipper - Dev Launcher (Linux)
# Kills anything on ports 3000 + 8088, starts backend + frontend, opens browser

set -euo pipefail

FRONTEND_PORT=3007
BACKEND_PORT=8088
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/pc-flipper"
BACKEND_DIR="$SCRIPT_DIR/pc-flipper-backend"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"

kill_port() {
    local port=$1
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "  Killing PID(s) $pids on port $port"
        kill -9 $pids 2>/dev/null || true
    fi
}

echo ""
echo "  PC Flipper Dev Launcher"
echo "  ---------------------------------"
echo ""

# 1 - Free ports
echo "[1/4] Freeing ports and stale processes..."
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
sleep 0.5

# 2 - Start backend
echo "[2/4] Starting backend  (port $BACKEND_PORT)..."

if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "  venv not found - installing..."
    python3 -m venv "$BACKEND_DIR/.venv"
    "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements-dev.txt" -q
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "  Created .env from .env.example — edit it to add API keys"
fi

gnome-terminal --title="PC Flipper Backend" -- bash -c "
  cd '$BACKEND_DIR'
  echo 'Backend running on port $BACKEND_PORT'
  .venv/bin/python -m uvicorn app.main:app --port $BACKEND_PORT --host 0.0.0.0 --reload
  exec bash
" 2>/dev/null || \
xterm -title "PC Flipper Backend" -e bash -c "
  cd '$BACKEND_DIR'
  echo 'Backend running on port $BACKEND_PORT'
  .venv/bin/python -m uvicorn app.main:app --port $BACKEND_PORT --host 0.0.0.0 --reload
  exec bash
" &

# 3 - Start frontend
echo "[3/4] Starting frontend (port $FRONTEND_PORT)..."

gnome-terminal --title="PC Flipper Frontend" -- bash -c "
  cd '$FRONTEND_DIR'
  echo 'Frontend running on port $FRONTEND_PORT'
  npm run dev
  exec bash
" 2>/dev/null || \
xterm -title "PC Flipper Frontend" -e bash -c "
  cd '$FRONTEND_DIR'
  echo 'Frontend running on port $FRONTEND_PORT'
  npm run dev
  exec bash
" &

# 4 - Poll until ready then open browser
echo "[4/4] Waiting for frontend..."

TIMEOUT=60
ELAPSED=0
READY=false

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if curl -sf --max-time 2 "$FRONTEND_URL" > /dev/null 2>&1; then
        READY=true
        break
    fi
    echo "  ...waiting (${ELAPSED}s)"
done

echo ""
if [ "$READY" = true ]; then
    echo "  Ready! Opening $FRONTEND_URL"
else
    echo "  Timed out - opening anyway"
fi

xdg-open "$FRONTEND_URL" 2>/dev/null || open "$FRONTEND_URL" 2>/dev/null || true

echo ""
echo "  Frontend : $FRONTEND_URL"
echo "  Backend  : http://localhost:$BACKEND_PORT/docs"
echo ""
