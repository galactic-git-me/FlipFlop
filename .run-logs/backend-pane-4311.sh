#!/usr/bin/env bash
set +e
echo "Backend dashboard (Rich): http://andromeda-ts:4311"
echo "API base: http://andromeda-ts:4311/api"
echo "Backend log file: /home/mac/CODING/FlipFlop/.run-logs/backend-4311.log"
echo
if [[ -x "/home/mac/CODING/FlipFlop/pc-flipper-backend/.venv/bin/python" ]] && "/home/mac/CODING/FlipFlop/pc-flipper-backend/.venv/bin/python" -c "from rich.console import Console" >/dev/null 2>&1; then
  "/home/mac/CODING/FlipFlop/pc-flipper-backend/.venv/bin/python" "/home/mac/CODING/FlipFlop/pc-flipper-backend/scripts/backend_console_dashboard.py" --base-url "http://andromeda-ts:4311"
else
  python3 "/home/mac/CODING/FlipFlop/pc-flipper-backend/scripts/backend_console_dashboard.py" --base-url "http://andromeda-ts:4311"
fi
code=$?
echo
echo "[warn] Rich backend dashboard exited (status: $code). Falling back to backend logs..."
echo
tail -n 240 -f "/home/mac/CODING/FlipFlop/.run-logs/backend-4311.log"
