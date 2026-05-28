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
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

# ── Shared state ───────────────────────────────────────────────────────────────
_LOG_BUFFER: deque[dict] = deque(maxlen=2000)
_WAITERS: list[asyncio.Queue] = []
_LONDON_TZ = ZoneInfo("Europe/London")

_INSTALLED = False


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


@router.get("/stream")
async def stream_logs():
    """
    Server-Sent Events stream.  On connect the client receives the buffered
    history first, then live events as they arrive.  A keepalive comment is
    sent every 15 s so load balancers don't drop idle connections.
    """
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
