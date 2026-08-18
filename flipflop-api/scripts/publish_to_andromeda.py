"""Publish the allow-listed customer catalogue to Andromeda over SSH."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.production_catalogue_sync import export_snapshot


REMOTE_ROOT = "/home/mac/CODING/FlipFlop"


def publish(host: str) -> None:
    with tempfile.TemporaryDirectory(prefix="flipflop-production-sync-") as folder:
        snapshot = Path(folder) / "catalogue.json"
        export_snapshot(snapshot)
        subprocess.run(
            ["scp", str(snapshot), f"{host}:{REMOTE_ROOT}/catalogue-sync.json"],
            check=True,
        )
        remote = (
            f"docker cp {REMOTE_ROOT}/catalogue-sync.json "
            "flipflop-production-api:/tmp/catalogue-sync.json && "
            "docker exec flipflop-production-api python -m "
            "app.services.production_catalogue_sync import /tmp/catalogue-sync.json && "
            f"rm -f {REMOTE_ROOT}/catalogue-sync.json && "
            "docker exec flipflop-production-api rm -f /tmp/catalogue-sync.json"
        )
        subprocess.run(["ssh", "-T", host, remote], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=900)
    parser.add_argument(
        "--host",
        default=os.getenv("FLIPFLOP_PRODUCTION_SSH_HOST", "andromeda"),
    )
    args = parser.parse_args()
    while True:
        try:
            publish(args.host)
            print("[OK] Production catalogue snapshot published", flush=True)
        except Exception as exc:
            print(f"[WARN] Production catalogue publish failed: {exc}", flush=True)
        if not args.watch:
            break
        time.sleep(max(60, args.interval))


if __name__ == "__main__":
    main()
