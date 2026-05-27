#!/usr/bin/env bash
set +e
echo "Alerts / Errors (backend + frontend)"
echo "Backend : /home/mac/CODING/FlipFlop/.run-logs/backend-4311.log"
echo "Frontend: /home/mac/CODING/FlipFlop/.run-logs/frontend-4310.log"
echo
touch "/home/mac/CODING/FlipFlop/.run-logs/backend-4311.log" "/home/mac/CODING/FlipFlop/.run-logs/frontend-4310.log"
tail -n 120 -f "/home/mac/CODING/FlipFlop/.run-logs/backend-4311.log" "/home/mac/CODING/FlipFlop/.run-logs/frontend-4310.log" | grep --line-buffered -Ei "error|warn|failed|exception|traceback|critical|429|403"
