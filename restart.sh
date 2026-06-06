#!/bin/bash
set -e

COMPOSE_FILE="$(dirname "$0")/docker-compose.yml"

echo "Stopping containers..."
docker compose -f "$COMPOSE_FILE" down

echo "Building and starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "Status:"
docker compose -f "$COMPOSE_FILE" ps
