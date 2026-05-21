#!/usr/bin/env bash
set +e
if python3 -c "from rich.console import Console" >/dev/null 2>&1; then
  python3 "/home/mac/CODING/FlipFlop/scripts/rich_tail.py" --title "Backend Logs" --file "/home/mac/CODING/FlipFlop/.run-logs/backend-4311.log" --lines 180
else
  echo "Backend logs: /home/mac/CODING/FlipFlop/.run-logs/backend-4311.log"
  echo
  tail -n 240 -f "/home/mac/CODING/FlipFlop/.run-logs/backend-4311.log" | sed -u     -e 's/\(ERROR\|Error\|error\|FAILED\|failed\)/\x1b[31m&\x1b[0m/g'     -e 's/\(WARN\|Warn\|warn\)/\x1b[33m&\x1b[0m/g'     -e 's/\(INFO\|Info\|info\)/\x1b[36m&\x1b[0m/g'
fi
