#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$DIR/docker-compose.yml"

echo "Stopping containers..."
docker compose -f "$COMPOSE_FILE" down

echo "Building and starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "Status:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "Waiting for backend to be ready..."
until curl -sf http://localhost:4311/health > /dev/null 2>&1; do
  sleep 1
done

echo ""
# OSC 8 hyperlink — clickable in most modern terminals (iTerm2, Windows Terminal, GNOME Terminal)
printf "\e]8;;http://localhost:4310\e\\  \U0001F310  Frontend: http://localhost:4310\e]8;;\e\\\n"
echo ""

echo "Launching rich dashboard..."
python3 "$DIR/scripts/rich_dashboard.py" \
  --base-url http://localhost:4311 \
  --docker-container flipflop-backend
