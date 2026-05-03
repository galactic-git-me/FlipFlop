#!/usr/bin/env bash
# Start the backend (assumes PostgreSQL + Redis are running via docker-compose or natively)
set -e

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

echo "Starting PC Flipper Backend on http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
