from __future__ import annotations

from collections import deque
from contextvars import ContextVar
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4

_ctx_source: ContextVar[str | None] = ContextVar("telemetry_source", default=None)
_ctx_run_id: ContextVar[str | None] = ContextVar("telemetry_run_id", default=None)

_records: deque[dict[str, Any]] = deque(maxlen=12000)
_lock = Lock()


def begin_source_run(source_name: str) -> str:
    run_id = str(uuid4())
    _ctx_source.set(source_name)
    _ctx_run_id.set(run_id)
    return run_id


def end_source_run() -> None:
    _ctx_source.set(None)
    _ctx_run_id.set(None)


def record_term_result(
    *,
    term: str,
    found: int = 0,
    new: int = 0,
    error: str | None = None,
    source_name: str | None = None,
    run_id: str | None = None,
) -> None:
    source = source_name or _ctx_source.get()
    rid = run_id or _ctx_run_id.get()
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "run_id": rid,
        "source": source,
        "term": term,
        "found": int(found),
        "new": int(new),
        "error": error,
    }
    with _lock:
        _records.append(entry)


def latest_records(limit: int = 500) -> list[dict[str, Any]]:
    with _lock:
        return list(_records)[-max(1, min(limit, 5000)):]


def latest_by_source(limit: int = 1000) -> dict[str, list[dict[str, Any]]]:
    rows = latest_records(limit=limit)
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        source = row.get("source") or "unknown"
        out.setdefault(source, []).append(row)
    return out
