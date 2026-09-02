#!/usr/bin/env bash
# Deploys the standalone peer_sync.py module to Andromeda and registers it
# as a restart-safe systemd --user service. Run this FROM Windows via:
#   scp flipflop-api/app/services/peer_sync.py andromeda:~/peer-sync/peer_sync.py
#   ssh andromeda 'bash -s' < scripts/deploy-peer-sync-andromeda.sh
# (the scp must run first / separately -- this script only sets up the venv
# and service, it does not copy itself over stdin). Idempotent.
set -euo pipefail

TARGET_DIR="$HOME/peer-sync"
mkdir -p "$TARGET_DIR"

if [ ! -d "$TARGET_DIR/venv" ]; then
    python3 -m venv "$TARGET_DIR/venv"
fi
"$TARGET_DIR/venv/bin/pip" install --quiet --upgrade pip
"$TARGET_DIR/venv/bin/pip" install --quiet sqlalchemy psycopg2-binary

mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/peer-sync.service" <<'UNIT'
[Unit]
Description=FlipFlop peer database sync (andromeda side)
After=network-online.target

[Service]
Type=simple
ExecStart=%h/peer-sync/venv/bin/python %h/peer-sync/peer_sync.py --write
Restart=always
RestartSec=10
Environment=DATABASE_URL=postgresql://flipper:flipper@172.23.0.3:5432/pcflipper
Environment=PEER_DATABASE_URL=postgresql://flipper:flipper@127.0.0.1:15433/pcflipper
Environment=PEER_SYNC_NODE=andromeda
Environment=PEER_SYNC_INTERVAL_SECONDS=30

[Install]
WantedBy=default.target
UNIT

sudo loginctl enable-linger "$(whoami)"
systemctl --user daemon-reload
systemctl --user enable peer-sync.service
systemctl --user restart peer-sync.service
systemctl --user status peer-sync.service --no-pager
