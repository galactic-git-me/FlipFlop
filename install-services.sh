#!/usr/bin/env bash
# Install PC Flipper as systemd services that start on boot.
# Run once: sudo ./install-services.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/pc-flipper-backend"
FRONTEND_DIR="$SCRIPT_DIR/pc-flipper"
SYSTEMD_DIR="/etc/systemd/system"

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

# --- Backend venv ---
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "Creating backend venv..."
    python3 -m venv "$BACKEND_DIR/.venv"
    "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt" -q
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "Created $BACKEND_DIR/.env — edit it to add API keys before starting the service."
fi

# --- Frontend build ---
echo "Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install --silent

# --- Copy service files ---
echo "Installing systemd units..."
cp "$BACKEND_DIR/pc-flipper-backend.service" "$SYSTEMD_DIR/"
cp "$FRONTEND_DIR/pc-flipper-frontend.service" "$SYSTEMD_DIR/"

systemctl daemon-reload
systemctl enable pc-flipper-backend.service
systemctl enable pc-flipper-frontend.service

echo ""
echo "Services installed and enabled."
echo ""
echo "  Start now : sudo systemctl start pc-flipper-backend pc-flipper-frontend"
echo "  Status    : sudo systemctl status pc-flipper-backend pc-flipper-frontend"
echo "  Logs      : journalctl -u pc-flipper-frontend -u pc-flipper-backend -f"
echo "  Frontend  : http://localhost:3007"
echo "  Backend   : http://localhost:8088/docs"
echo ""
