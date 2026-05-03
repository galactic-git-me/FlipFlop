#!/usr/bin/env bash
# PC Flipper - Dev Launcher (Linux)
# Starts backend (port 8088) and frontend (port 3007) in the background.
# Logs: /tmp/pcflipper-backend.log  /tmp/pcflipper-frontend.log

FRONTEND_PORT=3007
BACKEND_PORT=8088
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/pc-flipper"
BACKEND_DIR="$SCRIPT_DIR/pc-flipper-backend"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"
BACKEND_LOG="/tmp/pcflipper-backend.log"
FRONTEND_LOG="/tmp/pcflipper-frontend.log"

kill_port() {
    local pids
    pids=$(lsof -ti :"$1" 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
}

echo ""
echo "  PC Flipper Dev Launcher"
echo "  ---------------------------------"
echo ""

# 1 - Free ports
echo "[1/4] Freeing ports $BACKEND_PORT and $FRONTEND_PORT..."
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
sleep 0.5

# 2 - Backend setup
echo "[2/4] Starting backend  (port $BACKEND_PORT)..."

if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "  venv not found — installing dependencies..."
    python3 -m venv "$BACKEND_DIR/.venv"
    sudo "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt" -q
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
    if [ -f "$BACKEND_DIR/.env.example" ]; then
        cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    else
        touch "$BACKEND_DIR/.env"
    fi
    echo "  Created $BACKEND_DIR/.env — add API keys as needed."
fi

(cd "$BACKEND_DIR" && .venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" --reload \
    > "$BACKEND_LOG" 2>&1) &
BACKEND_PID=$!
echo "  Backend PID $BACKEND_PID  →  logs: $BACKEND_LOG"

# 3 - Frontend
echo "[3/4] Starting frontend (port $FRONTEND_PORT)..."

(cd "$FRONTEND_DIR" && PORT=$FRONTEND_PORT npm run dev \
    > "$FRONTEND_LOG" 2>&1) &
FRONTEND_PID=$!
echo "  Frontend PID $FRONTEND_PID  →  logs: $FRONTEND_LOG"

# 4 - Poll until ready then open browser
echo "[4/4] Waiting for frontend..."

TIMEOUT=90
ELAPSED=0

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if curl -sf --max-time 2 "$FRONTEND_URL" > /dev/null 2>&1; then
        break
    fi
    echo "  ...waiting (${ELAPSED}s)"
done

echo ""
if curl -sf --max-time 2 "$FRONTEND_URL" > /dev/null 2>&1; then
    echo "  Ready! Opening $FRONTEND_URL"
else
    echo "  Timed out — opening anyway (check logs if blank)"
fi

xdg-open "$FRONTEND_URL" 2>/dev/null || true

echo ""
echo "  Frontend : $FRONTEND_URL          (PID $FRONTEND_PID)"
echo "  Backend  : http://localhost:$BACKEND_PORT/docs  (PID $BACKEND_PID)"
echo ""
echo "  Tail logs:"
echo "    tail -f $BACKEND_LOG"
echo "    tail -f $FRONTEND_LOG"
echo ""
echo "  Stop everything:"
echo "    kill $BACKEND_PID $FRONTEND_PID"
echo ""
