#!/bin/bash
# Run gemradar-api in WSL so it can reach Ollama Docker on localhost:11500

cd /mnt/c/Users/mclar/CODING/FlipFlop/flipflop-api || exit 1

# Ensure venv exists and is activated
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

# Set environment and start
export OLLAMA_BASE_URL=http://localhost:11500
export PYTHONUNBUFFERED=1

echo "Starting gemradar-api in WSL..."
echo "OLLAMA_BASE_URL=$OLLAMA_BASE_URL"

python -m uvicorn app.gem_radar_standalone:app --host 0.0.0.0 --port 18000
