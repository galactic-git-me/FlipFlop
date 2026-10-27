"""Run API tests in a uniquely created local PostgreSQL database.

Set FLIPFLOP_TEST_ADMIN_DATABASE_URL to a local PostgreSQL maintenance-database
connection (usually the `postgres` database). The generated test database is
removed only after migrations and the complete requested pytest command pass.
On failure it is retained for diagnosis and its name is printed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine


API_ROOT = Path(__file__).resolve().parents[1]
DATABASE_NAME_PATTERN = re.compile(r"^flipflop_test_[a-f0-9]{24}_test$")


def local_admin_connection():
    raw_url = os.environ.get("FLIPFLOP_TEST_ADMIN_DATABASE_URL", "")
    if not raw_url:
        raise SystemExit(
            "Set FLIPFLOP_TEST_ADMIN_DATABASE_URL to a local PostgreSQL "
            "maintenance database before running tests."
        )
    url = make_url(raw_url)
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg2"}
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.database != "postgres"
    ):
        raise SystemExit(
            "The test database administrator connection must use PostgreSQL "
            "on localhost or 127.0.0.1 and connect to the 'postgres' "
            "maintenance database."
        )
    psycopg_url = url.set(drivername="postgresql").render_as_string(hide_password=False)
    return psycopg2.connect(psycopg_url)


def create_database(admin, database_name: str) -> None:
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))


def mark_database(test_url, run_token: str) -> None:
    connection_url = test_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg2.connect(connection_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE flipflop_test_run_marker (run_token UUID PRIMARY KEY)"
            )
            cursor.execute(
                "INSERT INTO flipflop_test_run_marker (run_token) VALUES (%s)",
                (run_token,),
            )


def verify_migration_head(test_url) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    expected = sorted(ScriptDirectory.from_config(config).get_heads())
    engine = create_engine(test_url.set(drivername="postgresql"))
    try:
        with engine.connect() as connection:
            actual = sorted(MigrationContext.configure(connection).get_current_heads())
            if actual != expected:
                raise RuntimeError(f"Disposable database migration state is {actual}; expected Alembic heads {expected}")
    finally:
        engine.dispose()


def drop_database(admin, database_name: str) -> None:
    if not DATABASE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Refusing to drop a database outside this runner's unique namespace")
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (database_name,),
        )
        cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))


def run(command: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=API_ROOT, env=env, check=False)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="optional pytest arguments, for example: tests/test_orders.py -q",
    )
    args = parser.parse_args()
    if args.pytest_args[:1] == ["--"]:
        args.pytest_args = args.pytest_args[1:]

    admin = local_admin_connection()
    database_name = f"flipflop_test_{uuid4().hex[:24]}_test"
    run_token = str(uuid4())
    test_async_url = make_url(os.environ["FLIPFLOP_TEST_ADMIN_DATABASE_URL"])
    test_async_url = test_async_url.set(drivername="postgresql+asyncpg", database=database_name)
    test_sync_url = test_async_url.set(drivername="postgresql")
    env = os.environ.copy()
    env.update(
        {
            "FLIPFLOP_TEST_DATABASE_URL": test_async_url.render_as_string(hide_password=False),
            "DATABASE_URL": test_async_url.render_as_string(hide_password=False),
            "TEST_DATABASE_URL": test_async_url.render_as_string(hide_password=False),
            "SYNC_DATABASE_URL": test_sync_url.render_as_string(hide_password=False),
            "TEST_DATABASE_SCHEMA": "flipflop_test",
            "FLIPFLOP_TEST_RUN_TOKEN": run_token,
            "APP_ENV": "test",
            "FLIPFLOP_RUNTIME_ENV": "test",
            # API tests may start TestClient lifespans. Keep those web-only so
            # they cannot launch schedulers, workers or provider preflights.
            "WEB_ONLY": "true",
        }
    )

    created = False
    passed = False
    try:
        create_database(admin, database_name)
        created = True
        mark_database(test_async_url, run_token)
        run([sys.executable, "-m", "alembic", "upgrade", "head"], env)
        verify_migration_head(test_sync_url)
        pytest_args = args.pytest_args or ["tests"]
        run([sys.executable, "-m", "pytest", *pytest_args], env)
        passed = True
        return 0
    except subprocess.CalledProcessError as error:
        print(f"Command failed with exit code {error.returncode}; test database retained: {database_name}")
        return error.returncode
    finally:
        if created and passed:
            try:
                drop_database(admin, database_name)
            except Exception as error:  # retain the database and report cleanup failure
                print(f"Tests passed, but disposable database cleanup failed: {database_name}: {error}")
        admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
