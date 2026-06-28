from __future__ import annotations

import asyncio
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models.search_telemetry import SearchTelemetry
from app.models.source_search_term import SourceSearchTerm
from app.services.alerts import emit_alert

_ctx_source: ContextVar[str | None] = ContextVar("telemetry_source", default=None)
_ctx_run_id: ContextVar[str | None] = ContextVar("telemetry_run_id", default=None)

_records: deque[dict[str, Any]] = deque(maxlen=12000)
_lock = Lock()
_last_prune_ts: datetime | None = None
_last_zero_term_cleanup_ts: datetime | None = None


def begin_source_run(source_name: str) -> str:
    _maybe_schedule_prune()
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
    _schedule_db_persist(entry)


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


def _schedule_db_persist(entry: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_entry(entry))
    except RuntimeError:
        # Called without a running event loop (tests / scripts): persist synchronously.
        try:
            asyncio.run(_persist_entry(entry))
        except Exception:
            return


async def _persist_entry(entry: dict[str, Any]) -> None:
    try:
        async with AsyncSessionLocal() as db:
            row = SearchTelemetry(
                ts=datetime.utcnow(),
                run_id=entry.get("run_id"),
                source=entry.get("source"),
                term=str(entry.get("term") or ""),
                found=int(entry.get("found") or 0),
                new=int(entry.get("new") or 0),
                error=entry.get("error"),
            )
            db.add(row)
            await db.commit()
        await _maybe_cleanup_zero_terms()
    except Exception:
        # Never block the scrape path on telemetry persistence errors.
        return


def _maybe_schedule_prune(retention_days: int = 14) -> None:
    global _last_prune_ts
    now = datetime.utcnow()
    if _last_prune_ts and (now - _last_prune_ts) < timedelta(minutes=30):
        return
    _last_prune_ts = now
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_prune_old(retention_days))
    except RuntimeError:
        return


async def _prune_old(retention_days: int) -> None:
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(SearchTelemetry).where(SearchTelemetry.ts < cutoff))
            await db.commit()
    except Exception:
        return


def _scope_prefix(scope: str) -> str:
    if scope == "cases":
        return "Cases:"
    if scope == "accessories":
        return "Accessories:"
    if scope == "upgrade_parts":
        return "UpgradeParts:"
    return ""


def _row_sources(row: SourceSearchTerm) -> list[str]:
    scope = str(row.scope or "").strip().lower()
    prefix = _scope_prefix(scope)
    out: list[str] = []
    for src in (row.source_names or []):
        s = str(src or "").strip()
        if not s:
            continue
        out.append(f"{prefix}{s}" if prefix else s)
    return list(dict.fromkeys(out))


async def _maybe_cleanup_zero_terms(window_days: int = 3, cadence_minutes: int = 60) -> None:
    global _last_zero_term_cleanup_ts
    now = datetime.utcnow()
    if _last_zero_term_cleanup_ts and (now - _last_zero_term_cleanup_ts) < timedelta(minutes=cadence_minutes):
        return
    _last_zero_term_cleanup_ts = now
    await _cleanup_zero_terms(window_days=window_days)


async def _cleanup_zero_terms(window_days: int = 3) -> None:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    try:
        async with AsyncSessionLocal() as db:
            terms = (
                await db.execute(
                    select(SourceSearchTerm).where(SourceSearchTerm.enabled == True)  # noqa: E712
                )
            ).scalars().all()

            deleted_rows: list[SourceSearchTerm] = []
            for row in terms:
                term_txt = str(row.term or "").strip()
                if not term_txt:
                    continue
                sources = _row_sources(row)
                if not sources:
                    continue

                telem_rows = (
                    await db.execute(
                        select(SearchTelemetry).where(
                            SearchTelemetry.ts >= cutoff,
                            SearchTelemetry.term == term_txt,
                            SearchTelemetry.source.in_(sources),
                        )
                    )
                ).scalars().all()

                if not telem_rows:
                    continue

                covered_sources = {str(t.source or "") for t in telem_rows if str(t.source or "")}
                if not set(sources).issubset(covered_sources):
                    continue

                has_positive = any(int(t.found or 0) > 0 for t in telem_rows)
                has_error = any(str(t.error or "").strip() for t in telem_rows)
                if has_positive or has_error:
                    continue

                await db.delete(row)
                deleted_rows.append(row)

            await db.commit()

        for row in deleted_rows:
            await emit_alert(
                code="auto_deleted_zero_search_term",
                source="search_terms",
                severity="warning",
                message=(
                    f"Auto-deleted search term '{row.term}' ({row.scope}) after "
                    f"{window_days} days of zero results across all configured vendors."
                ),
            )
    except Exception:
        return


async def latest_records_db(limit: int = 500) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 5000))
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SearchTelemetry).order_by(SearchTelemetry.ts.desc()).limit(lim)
        )
        rows = list(result.scalars().all())

    rows.reverse()
    return [
        {
            "ts": r.ts.isoformat() if r.ts else None,
            "run_id": r.run_id,
            "source": r.source,
            "term": r.term,
            "found": r.found,
            "new": r.new,
            "error": r.error,
        }
        for r in rows
    ]


async def latest_by_source_db(limit: int = 1000) -> dict[str, list[dict[str, Any]]]:
    rows = await latest_records_db(limit=limit)
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        source = row.get("source") or "unknown"
        out.setdefault(source, []).append(row)
    return out
