"""
In-memory log capture + SSE stream.

install_log_capture() must be called once at startup (before any other
structlog usage). It prepends a processor that funnels every rendered log
event into a capped deque. The deque is served via:

  GET /api/logs/history?tail=200   – last N lines as JSON
  GET /api/logs/stream             – SSE stream of live + buffered lines
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.gem_radar_sold_observation import GemRadarSoldObservation

# ── Shared state ───────────────────────────────────────────────────────────────
_LOG_BUFFER: deque[dict] = deque(maxlen=2000)
_WAITERS: list[asyncio.Queue] = []
_LONDON_TZ = ZoneInfo("Europe/London")

_INSTALLED = False

# The API runs from flipflop-api, while the development supervisor writes all
# service logs to the shared FlipFlop/logs directory. Resolve that directory
# from this file instead of relying on the process working directory.
_LOG_ROOT = Path(
    os.getenv(
        "FLIPFLOP_LOG_DIR",
        str(Path(__file__).resolve().parents[3] / "logs"),
    )
)

_LOG_TARGETS = {
    "api": {"label": "API server", "kind": "memory", "file": None},
    "gemradar": {"label": "Gem Radar server", "kind": "file", "file": str(_LOG_ROOT / "gemradar-api.out")},
    "admin": {"label": "Admin server", "kind": "file", "file": str(_LOG_ROOT / "admin-4312.out")},
    "frontend": {"label": "Frontend server", "kind": "file", "file": str(_LOG_ROOT / "frontend.log")},
    "worker": {"label": "Background worker", "kind": "file", "file": str(_LOG_ROOT / "backend-4311.out")},
}


def _target_file(target: str, mode: str) -> str | None:
    config = _LOG_TARGETS.get(target)
    if not config or config["kind"] != "file":
        return None
    env_key = f"{target.upper()}_LOG_FILE_{mode.upper()}"
    if os.getenv(env_key):
        return os.getenv(env_key)
    if mode.lower() in {"dev", "development"}:
        development_files = {
            "gemradar": _LOG_ROOT / "gem-radar-18000.out",
            "admin": _LOG_ROOT / "admin-4312.out",
            "frontend": _LOG_ROOT / "frontend.log",
            "worker": _LOG_ROOT / "backend-4311-dev-current.out",
        }
        return str(development_files.get(target, Path(config["file"])))
    return config["file"]


def _push(entry: dict) -> None:
    _LOG_BUFFER.append(entry)
    dead = []
    for q in _WAITERS:
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _WAITERS.remove(q)
        except ValueError:
            continue


def install_log_capture() -> None:
    """
    Prepend a structlog processor that copies every log event into our
    in-memory buffer. Safe to call multiple times — only installs once.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def _capture(logger, method: str, event_dict: dict) -> dict:
        _push({
            "ts":    datetime.now(_LONDON_TZ).isoformat(),
            "level": method,
            "msg":   str(event_dict.get("event", "")),
            "extra": {k: str(v) for k, v in event_dict.items() if k not in ("event",)},
        })
        return event_dict

    cfg = structlog.get_config()
    existing = list(cfg.get("processors", []))
    structlog.configure(processors=[_capture] + existing)


# ── Router ─────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/history")
async def get_log_history(tail: int = 300):
    """Return the last *tail* buffered log entries as JSON."""
    return list(_LOG_BUFFER)[-tail:]


@router.get("/targets")
async def get_log_targets():
    return [
        {
            "id": key,
            "label": value["label"],
            "available": value["kind"] == "memory"
            or Path(value["file"]).exists()
            or any(
                candidate.exists()
                for candidate in (
                    _LOG_ROOT / "gem-radar-18000.out",
                    _LOG_ROOT / "backend-4311-dev-current.out",
                )
                if key in {"gemradar", "worker"}
            ),
        }
        for key, value in _LOG_TARGETS.items()
    ]


@router.get("/stream")
async def stream_logs(target: str = "api", mode: str = "live"):
    """
    Server-Sent Events stream.  On connect the client receives the buffered
    history first, then live events as they arrive.  A keepalive comment is
    sent every 15 s so load balancers don't drop idle connections.
    """
    config = _LOG_TARGETS.get(target, _LOG_TARGETS["api"])
    if config["kind"] == "file":
        path = Path(_target_file(target, mode) or config["file"])

        async def file_generate():
            position = 0
            while True:
                if path.exists():
                    with path.open("r", encoding="utf-8", errors="replace") as handle:
                        handle.seek(position)
                        for raw in handle:
                            line = raw.rstrip()
                            if line:
                                yield f"data: {json.dumps({'ts': datetime.now(_LONDON_TZ).isoformat(), 'level': 'info', 'msg': line, 'extra': {}, 'target': target})}\n\n"
                        position = handle.tell()
                await asyncio.sleep(1)

        return StreamingResponse(file_generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _WAITERS.append(q)

    async def generate():
        try:
            # Replay existing buffer
            for entry in list(_LOG_BUFFER):
                yield f"data: {json.dumps(entry)}\n\n"
            # Stream live entries
            while True:
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            return
        finally:
            try:
                _WAITERS.remove(q)
            except ValueError:
                return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sold-scraping")
async def sold_scraping_log(limit: int = 100):
    """Return the durable sold-comps observations collected by the extension.

    The extension's progress table is intentionally ephemeral, but the actual
    completed-sale rows are persisted and reused by pricing and demand.
    """
    limit = max(1, min(limit, 500))
    async with AsyncSessionLocal() as db:
        rows = list((await db.execute(
            select(GemRadarSoldObservation)
            .order_by(GemRadarSoldObservation.observed_at.desc())
            .limit(limit)
        )).scalars().all())
    return {
        "items": [{
            "id": row.id,
            "observed_at": row.observed_at.isoformat() if row.observed_at else None,
            "title": row.title or row.model or row.match_key,
            "match_key": row.match_key,
            "condition": row.condition,
            "price": row.price,
            "postage": row.postage,
            "source_url": row.source_url,
            "cpk": row.cpk,
            "identity_confidence": row.identity_confidence,
        } for row in rows],
        "stored_count": len(rows),
        "note": "Rows are deduplicated by canonical item and reused by price benchmarks and demand analysis.",
    }
