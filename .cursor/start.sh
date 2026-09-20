#!/usr/bin/env bash
# Per-boot startup for the FlipFlop Cloud Agent environment.
#
# Brings up the infrastructure daemons the app services depend on. The two
# application servers themselves run as named `terminals` (see
# .cursor/environment.json) so their logs stay visible and restartable.
set -euo pipefail

echo "==> Starting Postgres"
sudo pg_ctlcluster 16 main start 2>/dev/null || true

echo "==> Starting Redis"
sudo service redis-server start 2>/dev/null || true

echo "==> Waiting for Postgres to accept connections"
for _ in $(seq 1 30); do
  if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    echo "    Postgres is ready"
    break
  fi
  sleep 1
done
