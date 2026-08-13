#!/usr/bin/env bash
# Start the backend (assumes PostgreSQL + Redis are running via docker-compose or natively)
set -e

# Ensure OLLAMA is configured if available
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11500}"

# Wait for Ollama to be ready (if configured)
if [ -n "$OLLAMA_BASE_URL" ] && [ "$OLLAMA_BASE_URL" != "http://localhost:11500" ] || curl -s "$OLLAMA_BASE_URL/api/tags" > /dev/null 2>&1; then
  echo "✅ Ollama is ready at $OLLAMA_BASE_URL"
else
  echo "⚠️  Ollama not ready at $OLLAMA_BASE_URL (will use OpenRouter fallback)"
fi

# Copy .env if not present
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit it to add API keys"
fi

# Install deps if venv not present
if [ ! -d .venv ]; then
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

echo "Starting PC Flipper Backend on http://localhost:18000"
echo "OLLAMA_BASE_URL=$OLLAMA_BASE_URL"
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
