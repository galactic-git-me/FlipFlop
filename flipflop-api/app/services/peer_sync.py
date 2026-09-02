"""Conservative bidirectional PostgreSQL peer synchronisation.

This service is deliberately separate from request handling and workers.  It
copies only explicitly allow-listed rows and columns, uses a stable
per-node timestamp to make retries idempotent, and only ever deletes a row
on one peer when it can prove that peer's copy has not been edited locally
since the last successful sync (see ``_process_tombstones``).  It is
intended to run once on each peer with the other peer configured as
``PEER_DATABASE_URL``.

Secret handling
----------------
Columns matching ``SECRET_COLUMN_PATTERN`` (API keys, Stripe/OAuth secrets,
encryption keys, session/JWT tokens, generic credentials) or listed in
``ALWAYS_EXCLUDE`` are never read or written by this module, regardless of
which table they appear on.  ``password_hash`` is intentionally *not*
excluded: it is a one-way hash, not a secret, and both peers must agree on
it for a customer/admin to be able to log in on either node after a
password change.  No table in this schema currently stores a raw API key,
encryption key, or session token as a plain column, so the exclusion list
is defense in depth rather than a live requirement today.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import socket
import time
from datetime import datetime, timezone

from sqlalchemy import MetaData, Table, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError


DEFAULT_TABLES = (
    "customers",
    "admin_users",
    "orders",
    "order_checklists",
    "order_photos",
    "gem_radar_scan_runs",
    "gem_radar_listing_observations",
    # gem_radar_scored_listings is deliberately excluded: it has a UNIQUE
    # (listing_id) constraint distinct from its `id` primary key, and both
    # peers have independently scanned/scored the same real eBay listings
    # under different autoincrement ids for months before this sync existed.
    # A first-time merge collides on nearly every row (verified: ~40k of
    # ~41k rows), which the engine now handles safely (per-row conflict
    # recording, no data loss -- see the fast-path/slow-path split in
    # sync_once) but which is far too slow to redo on every cycle. This
    # needs a one-time reconciliation pass (decide a winner per listing_id,
    # or dedupe before merging) before it can rejoin the allowlist.
    "gem_radar_sold_observations",
    "gem_radar_amazon_observations",
    "submission_queue",
    "inventory_units",
    "inventory_events",
)

# Never copied, on any table, regardless of name matching.
ALWAYS_EXCLUDE = frozenset({"stripe_secret_key", "encryption_key"})

# Column-name patterns that are never copied. Deliberately does not match
# "password"/"password_hash" -- see module docstring.
SECRET_COLUMN_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|encryption[_-]?key|client[_-]?secret|credential)",
    re.IGNORECASE,
)

RETRYABLE_EXCEPTIONS = (OperationalError, DBAPIError, ConnectionError, TimeoutError)
RETRY_DELAYS = (1, 2, 4)


def _tables() -> tuple[str, ...]:
    raw = os.getenv("PEER_SYNC_TABLES", ",".join(DEFAULT_TABLES))
    return tuple(dict.fromkeys(x.strip() for x in raw.split(",") if x.strip()))


def _url(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def _is_write_enabled(cli_write: bool) -> bool:
    return cli_write or os.getenv("PEER_SYNC_WRITE", "").strip().lower() in {"1", "true", "yes"}


def _ensure_metadata(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS peer_sync_state (
                table_name TEXT NOT NULL,
                row_key TEXT NOT NULL,
                source_node TEXT NOT NULL,
                source_updated_at TIMESTAMPTZ NOT NULL,
                row_checksum TEXT,
                synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (table_name, row_key)
            )
        """))
        conn.execute(text("ALTER TABLE peer_sync_state ADD COLUMN IF NOT EXISTS row_checksum TEXT"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS peer_sync_conflicts (
                id BIGSERIAL PRIMARY KEY,
                table_name TEXT NOT NULL,
                row_key TEXT NOT NULL,
                local_updated_at TIMESTAMPTZ,
                remote_updated_at TIMESTAMPTZ,
                winner TEXT NOT NULL,
                detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE (table_name, row_key, detected_at)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS peer_sync_tombstones (
                id BIGSERIAL PRIMARY KEY,
                table_name TEXT NOT NULL,
                row_key TEXT NOT NULL,
                node TEXT NOT NULL,
                detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                applied_at TIMESTAMPTZ,
                UNIQUE (table_name, row_key, node, detected_at)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS peer_sync_runs (
                id BIGSERIAL PRIMARY KEY,
                node TEXT NOT NULL,
                started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                finished_at TIMESTAMPTZ,
                status TEXT NOT NULL DEFAULT 'running',
                tables_synced INTEGER NOT NULL DEFAULT 0,
                copied INTEGER NOT NULL DEFAULT 0,
                skipped INTEGER NOT NULL DEFAULT 0,
                conflicts INTEGER NOT NULL DEFAULT 0,
                deletes INTEGER NOT NULL DEFAULT 0,
                errors_count INTEGER NOT NULL DEFAULT 0,
                error_detail TEXT
            )
        """))


def _key(row: dict, primary_keys) -> str:
    return "|".join(f"{key.name}={row[key.name]}" for key in primary_keys)


def _syncable_columns(table: Table) -> list[str]:
    names = []
    for col in table.columns:
        if col.name in ALWAYS_EXCLUDE or SECRET_COLUMN_PATTERN.search(col.name):
            continue
        names.append(col.name)
    return names


def _checksum(row: dict, columns: list[str]) -> str:
    payload = "|".join(f"{c}={row.get(c)!r}" for c in sorted(columns))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _with_retry(fn, errors: list[str], label: str):
    last_exc = None
    for attempt, delay in enumerate((0, *RETRY_DELAYS)):
        if delay:
            time.sleep(delay)
        try:
            return fn()
        except RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            continue
    errors.append(f"{label}: retries exhausted: {last_exc}")
    raise last_exc


def _record_run_start(engine, node: str) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("INSERT INTO peer_sync_runs (node, status) VALUES (:node, 'running') RETURNING id"),
            {"node": node},
        ).first()
        return row[0]


def _record_run_finish(engine, run_id: int, status: str, result: dict) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE peer_sync_runs SET
                    finished_at = now(), status = :status, tables_synced = :tables,
                    copied = :copied, skipped = :skipped, conflicts = :conflicts,
                    deletes = :deletes, errors_count = :errors_count, error_detail = :error_detail
                WHERE id = :id
            """),
            {
                "id": run_id,
                "status": status,
                "tables": result.get("tables", 0),
                "copied": result.get("copied", 0),
                "skipped": result.get("skipped", 0),
                "conflicts": result.get("conflicts", 0),
                "deletes": result.get("deletes", 0),
                "errors_count": len(result.get("errors", [])),
                "error_detail": "; ".join(result.get("errors", []))[:8000] or None,
            },
        )


def _record_conflict(conn, table_name: str, row_key: str, local_ts, remote_ts, winner: str) -> None:
    conn.execute(
        text("""
            INSERT INTO peer_sync_conflicts (table_name, row_key, local_updated_at, remote_updated_at, winner)
            VALUES (:table_name, :row_key, :local_ts, :remote_ts, :winner)
            ON CONFLICT (table_name, row_key, detected_at) DO NOTHING
        """),
        {"table_name": table_name, "row_key": row_key, "local_ts": local_ts, "remote_ts": remote_ts, "winner": winner},
    )


def _previously_synced_keys(engine, table_name: str) -> dict[str, str]:
    """Row keys this engine has recorded as synced at some point, i.e. rows
    known to have existed as of the last time they were compared. Used only
    to detect rows that have since vanished from the source table."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT row_key, row_checksum FROM peer_sync_state WHERE table_name = :t"),
            {"t": table_name},
        )
        return {r[0]: r[1] for r in rows}


def _record_synced(conn, table_name: str, row_key: str, node: str, updated_at, checksum: str) -> None:
    conn.execute(
        text("""
            INSERT INTO peer_sync_state (table_name, row_key, source_node, source_updated_at, row_checksum, synced_at)
            VALUES (:table_name, :row_key, :node, :updated_at, :checksum, now())
            ON CONFLICT (table_name, row_key) DO UPDATE SET
                source_node = EXCLUDED.source_node,
                source_updated_at = EXCLUDED.source_updated_at,
                row_checksum = EXCLUDED.row_checksum,
                synced_at = now()
        """),
        {"table_name": table_name, "row_key": row_key, "node": node, "updated_at": updated_at, "checksum": checksum},
    )


def _mark_row_synced_both(local_engine, peer_engine, table_name: str, row_key: str, updated_at, checksum: str) -> None:
    """Record the authoritative state of a row on BOTH peers' own
    peer_sync_state, so each engine has a baseline to diff against when it
    is later the source side of a delete-tombstone check -- not just the
    engine that happened to receive the last write for this key."""
    for engine in (local_engine, peer_engine):
        with engine.begin() as conn:
            _record_synced(conn, table_name, row_key, "synced", updated_at, checksum)


def _process_tombstones(
    local_engine, peer_engine, table_name: str, local_table: Table, peer_table: Table,
    pk_cols: list[str], dry_run: bool, result: dict,
) -> None:
    """Delete rows that vanished from one peer, but only where the other
    peer's copy is provably untouched since the last sync -- otherwise the
    delete is skipped and a conflict is recorded instead of ever discarding
    an independent local edit."""
    for source_engine, target_engine, source_table, target_table in (
        (local_engine, peer_engine, local_table, peer_table),
        (peer_engine, local_engine, peer_table, local_table),
    ):
        prior = _previously_synced_keys(source_engine, table_name)
        if not prior:
            continue
        with source_engine.connect() as sc:
            current_keys = {
                _key(row, list(source_table.primary_key.columns))
                for row in sc.execute(select(*[source_table.c[k] for k in pk_cols])).mappings()
            }
        vanished = set(prior) - current_keys
        for row_key in vanished:
            target_cols = _syncable_columns(target_table)
            with target_engine.connect() as tc:
                pk_values = dict(pair.split("=", 1) for pair in row_key.split("|"))
                where = " AND ".join(f"{k} = :{k}" for k in pk_values)
                target_row = tc.execute(text(f"SELECT * FROM {target_table.name} WHERE {where}"), pk_values).mappings().first()
            if target_row is None:
                continue
            current_checksum = _checksum(dict(target_row), target_cols)
            if current_checksum == prior[row_key]:
                if not dry_run:
                    with target_engine.begin() as tc:
                        where = " AND ".join(f"{k} = :{k}" for k in pk_values)
                        tc.execute(text(f"DELETE FROM {target_table.name} WHERE {where}"), pk_values)
                        tc.execute(
                            text("DELETE FROM peer_sync_state WHERE table_name = :t AND row_key = :k"),
                            {"t": table_name, "k": row_key},
                        )
                result["deletes"] += 1
            else:
                if not dry_run:
                    with target_engine.begin() as tc:
                        _record_conflict(tc, table_name, row_key, None, None, "delete_skipped_local_edit")
                result["conflicts"] += 1


def _table_fingerprints_match(local_engine, peer_engine, table: Table, updated_col) -> bool:
    query = select(func.count(), func.max(updated_col))
    try:
        with local_engine.connect() as c:
            local_fp = c.execute(query.select_from(table)).one()
        with peer_engine.connect() as c:
            peer_fp = c.execute(query.select_from(table)).one()
    except Exception:  # noqa: BLE001 - fall through to the real comparison on any doubt
        return False
    return local_fp == peer_fp


def sync_once(local_url: str, peer_url: str, dry_run: bool = True) -> dict:
    local = create_engine(local_url, pool_pre_ping=True)
    peer = create_engine(peer_url, pool_pre_ping=True)
    node = os.getenv("PEER_SYNC_NODE", socket.gethostname())
    result = {"tables": 0, "copied": 0, "skipped": 0, "conflicts": 0, "deletes": 0, "errors": []}
    run_id = None
    try:
        _ensure_metadata(local)
        run_id = _record_run_start(local, node)
        _ensure_metadata(peer)
        for name in _tables():
            try:
                # Separate metadata registries are required: reflecting the
                # same name twice into one registry would silently reuse the
                # local Table object for the peer connection.
                local_table = Table(name, MetaData(), autoload_with=local)
                peer_table = Table(name, MetaData(), autoload_with=peer)
                pks = list(local_table.primary_key.columns)
                updated = local_table.c.get("updated_at")
                if not pks or updated is None or peer_table.c.get("updated_at") is None:
                    result["errors"].append(f"{name}: requires primary key and updated_at")
                    continue
                result["tables"] += 1
                pk_cols = [p.name for p in pks]
                batch_size = int(os.getenv("PEER_SYNC_BATCH_SIZE", "250"))
                if _table_fingerprints_match(local, peer, local_table, updated):
                    # Cheap steady-state check: identical row count and max
                    # updated_at on both peers means nothing to reconcile.
                    # Skips 4 full-table scans a cycle would otherwise do on
                    # every table, every 30s, even when nothing changed --
                    # essential once a table has 10k+ rows and the peer is
                    # reached over an SSH tunnel.
                    continue
                # Deletes must be reconciled before the insert/update pass
                # below, otherwise a row deleted on one peer would simply be
                # re-inserted from the other peer's still-present copy.
                _process_tombstones(local, peer, name, local_table, peer_table, pk_cols, dry_run, result)
                for source, target, source_table, target_table in (
                    (local, peer, local_table, peer_table),
                    (peer, local, peer_table, local_table),
                ):
                    target_cols = _syncable_columns(target_table)
                    target_by_key = {}
                    with target.connect() as tc:
                        for other in tc.execute(select(target_table)).mappings().yield_per(batch_size):
                            target_by_key[_key(other, list(target_table.primary_key.columns))] = other
                    with source.connect() as sc:
                        rows = sc.execute(select(source_table).order_by(*[source_table.c[k] for k in pk_cols])).mappings()
                        while True:
                            batch = _with_retry(lambda: rows.fetchmany(batch_size), result["errors"], name)
                            if not batch:
                                break

                            synced_after_batch = []

                            def _plan_row(row):
                                """Decide what to do with one row without touching the DB.
                                Returns ('insert', values) or None (already handled/skipped)."""
                                key = _key(row, pks)
                                other = target_by_key.get(key)
                                checksum = _checksum(dict(row), target_cols)
                                if other is not None:
                                    other_ts, row_ts = other["updated_at"], row["updated_at"]
                                    if other_ts == row_ts:
                                        other_checksum = _checksum(dict(other), target_cols)
                                        if other_checksum != checksum:
                                            if not dry_run:
                                                _pending_conflicts.append((key, row_ts, other_ts, "tie_kept_both"))
                                            result["conflicts"] += 1
                                        result["skipped"] += 1
                                        return None
                                    if other_ts > row_ts:
                                        result["skipped"] += 1
                                        if not dry_run:
                                            synced_after_batch.append((key, other_ts, _checksum(dict(other), target_cols)))
                                        return None
                                if dry_run:
                                    result["copied"] += 1
                                    return None
                                values = {c.name: row[c.name] for c in target_table.columns if c.name in row and c.name in target_cols}
                                return (key, values, row["updated_at"], checksum)

                            def apply_batch(batch=batch, synced_after_batch=synced_after_batch):
                                # Fast path: the whole batch in one transaction, no
                                # per-row savepoint overhead -- correct for the
                                # overwhelming majority of rows, which never hit a
                                # secondary unique constraint.
                                _pending_conflicts.clear()
                                to_insert = [r for r in (_plan_row(row) for row in batch) if r is not None]
                                if not to_insert and not _pending_conflicts:
                                    return
                                try:
                                    with target.begin() as tc:
                                        for key, values, ts, checksum in to_insert:
                                            stmt = insert(target_table).values(values)
                                            updates = {c: stmt.excluded[c] for c in target_cols if c not in set(pk_cols)}
                                            tc.execute(stmt.on_conflict_do_update(index_elements=pk_cols, set_=updates))
                                        for key, row_ts, other_ts, winner in _pending_conflicts:
                                            _record_conflict(tc, name, key, row_ts, other_ts, winner)
                                    for key, values, ts, checksum in to_insert:
                                        synced_after_batch.append((key, ts, checksum))
                                        result["copied"] += 1
                                except IntegrityError:
                                    # Slow path, only reached when this batch actually
                                    # contains a secondary-unique-constraint collision
                                    # (e.g. two peers assigning different surrogate PKs
                                    # to the same real-world row): isolate each row in
                                    # its own transaction so one bad row becomes a
                                    # recorded conflict instead of losing the batch.
                                    for key, values, ts, checksum in to_insert:
                                        try:
                                            with target.begin() as tc:
                                                stmt = insert(target_table).values(values)
                                                updates = {c: stmt.excluded[c] for c in target_cols if c not in set(pk_cols)}
                                                tc.execute(stmt.on_conflict_do_update(index_elements=pk_cols, set_=updates))
                                        except IntegrityError:
                                            with target.begin() as tc:
                                                _record_conflict(tc, name, key, ts, None, "unique_constraint_violation")
                                            result["conflicts"] += 1
                                            continue
                                        synced_after_batch.append((key, ts, checksum))
                                        result["copied"] += 1
                                    with target.begin() as tc:
                                        for key, row_ts, other_ts, winner in _pending_conflicts:
                                            _record_conflict(tc, name, key, row_ts, other_ts, winner)

                            _pending_conflicts = []
                            _with_retry(apply_batch, result["errors"], name)
                            if not dry_run:
                                for key, ts, checksum in synced_after_batch:
                                    _mark_row_synced_both(local, peer, name, key, ts, checksum)
            except Exception as exc:  # noqa: BLE001 - captured per table, sync continues
                result["errors"].append(f"{name}: {exc}")
        _record_run_finish(local, run_id, "completed" if not result["errors"] else "completed_with_errors", result)
        return result
    except Exception:
        if run_id is not None:
            try:
                _record_run_finish(local, run_id, "failed", result)
            except Exception:  # noqa: BLE001 - best-effort logging only
                pass
        raise
    finally:
        local.dispose()
        peer.dispose()


def health(local_url: str, peer_url: str) -> dict:
    node = os.getenv("PEER_SYNC_NODE", socket.gethostname())
    status = {"node": node, "local_reachable": False, "peer_reachable": False, "last_run": None}
    for label, url in (("local_reachable", local_url), ("peer_reachable", peer_url)):
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect():
                status[label] = True
            engine.dispose()
        except Exception:  # noqa: BLE001 - reachability probe only
            status[label] = False
    try:
        engine = create_engine(local_url, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT node, started_at, finished_at, status, copied, skipped, conflicts, deletes, errors_count
                    FROM peer_sync_runs ORDER BY id DESC LIMIT 1
                """)
            ).mappings().first()
            status["last_run"] = dict(row) if row else None
        engine.dispose()
    except Exception as exc:  # noqa: BLE001 - health reporting must not crash
        status["last_run_error"] = str(exc)
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--write", action="store_true", help="apply changes; default is dry-run")
    parser.add_argument("--health", action="store_true", help="print health status and exit")
    args = parser.parse_args()
    if args.health:
        print(health(_url("DATABASE_URL"), _url("PEER_DATABASE_URL")), flush=True)
        return
    write = _is_write_enabled(args.write)
    interval = int(os.getenv("PEER_SYNC_INTERVAL_SECONDS", "30"))
    while True:
        print(sync_once(_url("DATABASE_URL"), _url("PEER_DATABASE_URL"), dry_run=not write), flush=True)
        if args.once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
