from types import SimpleNamespace

import pytest

from app.main import _ensure_additive_columns, _install_manual_build_delete_guard, _relax_listing_price_constraint


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _Connection:
    def __init__(self, *, existing_columns=(), guard_installed=False, dialect="postgresql"):
        self.dialect = SimpleNamespace(name=dialect)
        self.existing_columns = set(existing_columns)
        self.guard_installed = guard_installed
        self.ddl = []
        self.lookups = []

    async def execute(self, statement, params=None):
        params = params or {}
        self.lookups.append((str(statement), params))
        if "information_schema.columns" in str(statement):
            return _Result((params["table_name"], params["column_name"]) in self.existing_columns)
        return _Result(self.guard_installed)

    async def exec_driver_sql(self, statement):
        self.ddl.append(statement)


class _NullableConnection:
    def __init__(self, *, nullable):
        self.dialect = SimpleNamespace(name="postgresql")
        self.nullable = nullable
        self.ddl = []

    async def execute(self, statement, params=None):
        return _Result(self.nullable)

    async def exec_driver_sql(self, statement):
        self.ddl.append(statement)


@pytest.mark.asyncio
async def test_existing_additive_column_is_checked_without_reissuing_alter():
    conn = _Connection(existing_columns={("app_settings", "relist_interval_days")})

    await _ensure_additive_columns(conn, [
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS relist_interval_days INTEGER DEFAULT 7",
    ])

    assert conn.lookups[0][1] == {"table_name": "app_settings", "column_name": "relist_interval_days"}
    assert conn.ddl == []


@pytest.mark.asyncio
async def test_missing_additive_column_is_still_created():
    conn = _Connection()
    statement = "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS relist_interval_days INTEGER DEFAULT 7"

    await _ensure_additive_columns(conn, [statement])

    assert conn.ddl == [statement]


@pytest.mark.asyncio
async def test_installed_build_guards_are_not_dropped_and_recreated_at_startup():
    conn = _Connection(guard_installed=True)

    await _install_manual_build_delete_guard(conn)

    assert len(conn.lookups) == 1
    assert conn.ddl == []


@pytest.mark.asyncio
async def test_non_postgres_startup_skips_postgres_build_guard():
    conn = _Connection(dialect="sqlite")

    await _install_manual_build_delete_guard(conn)

    assert conn.lookups == []
    assert conn.ddl == []


@pytest.mark.asyncio
async def test_listing_price_constraint_is_relaxed_for_uncaptured_candidates():
    conn = _NullableConnection(nullable=False)

    await _relax_listing_price_constraint(conn)

    assert conn.ddl == ["ALTER TABLE listings ALTER COLUMN price DROP NOT NULL"]


@pytest.mark.asyncio
async def test_already_nullable_listing_price_does_not_reissue_ddl():
    conn = _NullableConnection(nullable=True)

    await _relax_listing_price_constraint(conn)

    assert conn.ddl == []
