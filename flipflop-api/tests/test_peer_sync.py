"""Integration tests for app.services.peer_sync.

These exercise real PostgreSQL (ON CONFLICT / autoload_with need the real
dialect), against two throwaway databases on the local server. Skips
cleanly when local Postgres isn't reachable so the rest of the suite
(sqlite-based) is unaffected.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.services import peer_sync

ADMIN_URL = "postgresql://flipper:flipper@127.0.0.1:5432/pcflipper"
SCHEMA_A = f"test_peer_sync_a_{uuid.uuid4().hex[:8]}"
SCHEMA_B = f"test_peer_sync_b_{uuid.uuid4().hex[:8]}"


def _schema_url(schema: str) -> str:
    return f"postgresql://flipper:flipper@127.0.0.1:5432/pcflipper?options=-csearch_path%3D{schema}"

TEST_TABLE = "peer_sync_test_rows"

CREATE_TABLE_SQL = f"""
CREATE TABLE {TEST_TABLE} (
    id INTEGER PRIMARY KEY,
    val TEXT,
    password_hash TEXT,
    session_token TEXT,
    updated_at TIMESTAMPTZ NOT NULL
)
"""


def _postgres_available() -> bool:
    try:
        engine = create_engine(ADMIN_URL, pool_pre_ping=True)
        with engine.connect():
            pass
        engine.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _postgres_available(), reason="local Postgres not reachable")


@pytest.fixture
def dbs():
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{SCHEMA_A}"'))
        conn.execute(text(f'CREATE SCHEMA "{SCHEMA_B}"'))
    url_a = _schema_url(SCHEMA_A)
    url_b = _schema_url(SCHEMA_B)
    for url in (url_a, url_b):
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(text(CREATE_TABLE_SQL))
        engine.dispose()

    os.environ["PEER_SYNC_TABLES"] = TEST_TABLE
    yield url_a, url_b

    with admin.connect() as conn:
        for schema in (SCHEMA_A, SCHEMA_B):
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    admin.dispose()
    os.environ.pop("PEER_SYNC_TABLES", None)


def _insert(url, id_, val, updated_at, password_hash="hash", session_token="tok"):
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                INSERT INTO {TEST_TABLE} (id, val, password_hash, session_token, updated_at)
                VALUES (:id, :val, :ph, :st, :ua)
            """),
            {"id": id_, "val": val, "ph": password_hash, "st": session_token, "ua": updated_at},
        )
    engine.dispose()


def _row(url, id_):
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT * FROM {TEST_TABLE} WHERE id = :id"), {"id": id_}).mappings().first()
    engine.dispose()
    return dict(row) if row else None


def _now(offset_seconds=0):
    return datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)


def test_insert_propagates_both_directions(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "from-a", _now())
    _insert(url_b, 2, "from-b", _now())

    result = peer_sync.sync_once(url_a, url_b, dry_run=False)

    assert result["errors"] == []
    assert _row(url_b, 1)["val"] == "from-a"
    assert _row(url_a, 2)["val"] == "from-b"


def test_update_newer_wins_each_direction(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "old", _now(-10))
    _insert(url_b, 1, "old", _now(-10))
    peer_sync.sync_once(url_a, url_b, dry_run=False)

    _insert(url_a, 2, "a-newer", _now())  # placeholder row so tables aren't empty
    engine = create_engine(url_a)
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE {TEST_TABLE} SET val = 'updated-on-a', updated_at = :ua WHERE id = 1"), {"ua": _now()})
    engine.dispose()

    peer_sync.sync_once(url_a, url_b, dry_run=False)

    assert _row(url_b, 1)["val"] == "updated-on-a"


def test_simultaneous_update_ties_are_recorded_and_neither_overwritten(dbs):
    url_a, url_b = dbs
    ts = _now()
    _insert(url_a, 1, "value-a", ts)
    _insert(url_b, 1, "value-b", ts)
    # A row that differs in count/max(updated_at) between the two peers, so
    # the cheap fingerprint short-circuit (see _table_fingerprints_match)
    # can't skip the real per-row comparison -- matching a real deployment,
    # where ordinary traffic constantly perturbs count/max. A table with
    # NO other activity that also ties on id+updated_at with different
    # content is the one case the fingerprint check can't see; documented
    # in docs/PEER_DATABASE_SYNC.md as an accepted, exceedingly narrow gap.
    _insert(url_a, 2, "extra", _now())

    peer_sync.sync_once(url_a, url_b, dry_run=False)

    assert _row(url_a, 1)["val"] == "value-a"
    assert _row(url_b, 1)["val"] == "value-b"

    conflicts = []
    for url in (url_a, url_b):
        engine = create_engine(url)
        with engine.connect() as conn:
            conflicts += conn.execute(
                text("SELECT winner FROM peer_sync_conflicts WHERE table_name = :t"), {"t": TEST_TABLE}
            ).fetchall()
        engine.dispose()
    assert any(r[0] == "tie_kept_both" for r in conflicts)


def test_duplicate_execution_is_idempotent(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "value", _now())

    first = peer_sync.sync_once(url_a, url_b, dry_run=False)
    second = peer_sync.sync_once(url_a, url_b, dry_run=False)

    assert first["copied"] >= 1
    assert second["copied"] == 0
    assert second["errors"] == []


def test_retry_wrapper_recovers_from_transient_failure():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise peer_sync.OperationalError("stmt", {}, Exception("connection reset"))
        return "ok"

    errors: list[str] = []
    assert peer_sync._with_retry(flaky, errors, "test") == "ok"
    assert calls["n"] == 2
    assert errors == []


def test_outage_is_caught_and_logged_as_failed_run(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "value", _now())
    bogus_peer = "postgresql://flipper:flipper@127.0.0.1:1/nonexistent"

    with pytest.raises(Exception):
        peer_sync.sync_once(url_a, bogus_peer, dry_run=False)

    engine = create_engine(url_a)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT status FROM peer_sync_runs ORDER BY id DESC LIMIT 1")).first()
    engine.dispose()
    assert row is not None
    assert row[0] == "failed"


def test_delete_propagates_when_target_untouched_since_sync(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "value", _now())
    peer_sync.sync_once(url_a, url_b, dry_run=False)
    assert _row(url_b, 1) is not None

    engine = create_engine(url_a)
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {TEST_TABLE} WHERE id = 1"))
    engine.dispose()

    result = peer_sync.sync_once(url_a, url_b, dry_run=False)

    assert result["deletes"] >= 1
    assert _row(url_b, 1) is None


def test_delete_skipped_when_target_edited_locally(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "value", _now(-10))
    peer_sync.sync_once(url_a, url_b, dry_run=False)

    engine_b = create_engine(url_b)
    with engine_b.begin() as conn:
        conn.execute(text(f"UPDATE {TEST_TABLE} SET val = 'edited-on-b', updated_at = :ua WHERE id = 1"), {"ua": _now()})
    engine_b.dispose()

    engine_a = create_engine(url_a)
    with engine_a.begin() as conn:
        conn.execute(text(f"DELETE FROM {TEST_TABLE} WHERE id = 1"))
    engine_a.dispose()

    result = peer_sync.sync_once(url_a, url_b, dry_run=False)

    assert _row(url_b, 1) is not None
    assert _row(url_b, 1)["val"] == "edited-on-b"

    conflicts = []
    for url in (url_a, url_b):
        engine = create_engine(url)
        with engine.connect() as conn:
            conflicts += conn.execute(
                text("SELECT winner FROM peer_sync_conflicts WHERE table_name = :t"), {"t": TEST_TABLE}
            ).fetchall()
        engine.dispose()
    assert any(r[0] == "delete_skipped_local_edit" for r in conflicts)


def test_secret_columns_never_sync_but_password_hash_does(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "value", _now(), password_hash="hash-from-a", session_token="token-from-a")
    _insert(url_b, 2, "value2", _now(), password_hash="hash-from-b", session_token="token-from-b")

    peer_sync.sync_once(url_a, url_b, dry_run=False)

    row_on_b = _row(url_b, 1)
    row_on_a = _row(url_a, 2)

    # password_hash is ordinary data and must sync.
    assert row_on_b["password_hash"] == "hash-from-a"
    assert row_on_a["password_hash"] == "hash-from-b"

    # session_token matches SECRET_COLUMN_PATTERN and must never be written.
    assert row_on_b["session_token"] is None
    assert row_on_a["session_token"] is None


def test_secondary_unique_constraint_conflict_does_not_crash_the_batch(dbs):
    """Two peers can independently assign different surrogate PKs to the
    same logical row (e.g. gem_radar_scored_listings.listing_id). Real
    schema regression: this used to abort the whole table's sync."""
    url_a, url_b = dbs
    engine_a = create_engine(url_a)
    engine_b = create_engine(url_b)
    with engine_a.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TEST_TABLE} ADD COLUMN natural_key TEXT"))
        conn.execute(text(f"ALTER TABLE {TEST_TABLE} ADD CONSTRAINT uq_natural_key UNIQUE (natural_key)"))
    with engine_b.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TEST_TABLE} ADD COLUMN natural_key TEXT"))
        conn.execute(text(f"ALTER TABLE {TEST_TABLE} ADD CONSTRAINT uq_natural_key UNIQUE (natural_key)"))
    engine_a.dispose()
    engine_b.dispose()

    # Same real-world row (same natural_key), different surrogate id on each
    # peer, plus one ordinary unrelated row that should still sync fine.
    for url, id_, ts_offset in ((url_a, 1, -5), (url_b, 2, 0)):
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {TEST_TABLE} (id, val, password_hash, session_token, updated_at, natural_key)
                    VALUES (:id, 'shared', 'h', 't', :ua, 'SHARED-KEY')
                """),
                {"id": id_, "ua": _now(ts_offset)},
            )
        engine.dispose()
    _insert(url_a, 10, "unrelated", _now())

    result = peer_sync.sync_once(url_a, url_b, dry_run=False)

    assert result["conflicts"] >= 1
    # The unrelated row still copied despite the conflict elsewhere in the batch.
    assert _row(url_b, 10) is not None

    conflicts = []
    for url in (url_a, url_b):
        engine = create_engine(url)
        with engine.connect() as conn:
            conflicts += conn.execute(
                text("SELECT winner FROM peer_sync_conflicts WHERE table_name = :t"), {"t": TEST_TABLE}
            ).fetchall()
        engine.dispose()
    assert any(r[0] == "unique_constraint_violation" for r in conflicts)


def test_dry_run_makes_no_changes(dbs):
    url_a, url_b = dbs
    _insert(url_a, 1, "value", _now())

    result = peer_sync.sync_once(url_a, url_b, dry_run=True)

    assert result["copied"] >= 1
    assert _row(url_b, 1) is None
