"""Process-local heartbeats for long-lived API background workers."""

from __future__ import annotations

import time
from datetime import datetime, timezone

_worker_heartbeats: dict[str, dict[str, tuple[float, datetime]]] = {}
_expected_workers: dict[str, int] = {}


def configure_worker_heartbeats(service: str, expected_workers: int) -> None:
    _expected_workers[service] = max(0, expected_workers)


def record_worker_heartbeat(service: str, worker_id: str) -> None:
    _worker_heartbeats.setdefault(service, {})[worker_id] = (time.monotonic(), datetime.now(timezone.utc))


def worker_heartbeat_status(service: str, *, stale_after_seconds: int = 30) -> dict[str, object]:
    now = time.monotonic()
    workers = _worker_heartbeats.get(service, {})
    online_workers = sorted(
        worker_id
        for worker_id, (last_seen, _) in workers.items()
        if now - last_seen <= stale_after_seconds
    )
    expected = _expected_workers.get(service, 0)
    last_heartbeat = max(
        (seen_at for _, seen_at in workers.values()),
        default=None,
    )
    return {
        "ok": expected > 0 and len(online_workers) == expected,
        "state": "online" if expected > 0 and len(online_workers) == expected else "degraded",
        "online_workers": len(online_workers),
        "expected_workers": expected,
        "stale_after_seconds": stale_after_seconds,
        "last_heartbeat_at": last_heartbeat.isoformat() if online_workers and last_heartbeat else None,
    }
