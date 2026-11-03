#!/usr/bin/env python3
"""Apply and validate Alembic migrations only against local DEV, then attest."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "flipflop-api"
MANIFEST = ROOT / "docs" / "database" / "dev-schema-validation.json"


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    print("+", " ".join(command))
    result = subprocess.run(command, cwd=cwd, env=env, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command[0]}")
    return "passed"


def main() -> int:
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError(
            "Commit the source and migration changes before creating a DEV validation record"
        )

    database_url = os.getenv(
        "PEER_LOCAL_DATABASE_URL",
        "postgresql://flipper:flipper@127.0.0.1:5432/pcflipper",
    )
    parsed = make_url(database_url)
    if (
        parsed.drivername.split("+")[0] not in {"postgres", "postgresql"}
        or parsed.host not in {"127.0.0.1", "localhost", "::1"}
        or parsed.database != "pcflipper"
    ):
        raise RuntimeError(
            "Refusing schema validation outside local DEV pcflipper on loopback"
        )

    env = os.environ.copy()
    env["SYNC_DATABASE_URL"] = parsed.set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    env["DATABASE_URL"] = parsed.set(drivername="postgresql+asyncpg").render_as_string(
        hide_password=False
    )

    # The test runner creates and destroys only a uniquely named disposable DB.
    # It never uses pcflipper as its test target.
    if not env.get("FLIPFLOP_TEST_ADMIN_DATABASE_URL"):
        from dotenv import dotenv_values

        local_env = dotenv_values(API / ".env.local")
        admin_user = local_env.get("LOCAL_POSTGRES_ADMIN_USER")
        admin_password = local_env.get("LOCAL_POSTGRES_ADMIN_PASSWORD")
        if not admin_user or not admin_password:
            raise RuntimeError(
                "Set FLIPFLOP_TEST_ADMIN_DATABASE_URL to a local PostgreSQL admin connection"
            )
        from sqlalchemy.engine import URL

        env["FLIPFLOP_TEST_ADMIN_DATABASE_URL"] = URL.create(
            "postgresql",
            username=admin_user,
            password=admin_password,
            host="127.0.0.1",
            port=5432,
            database="postgres",
        ).render_as_string(hide_password=False)

    run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=API, env=env)
    run(
        [
            sys.executable,
            "scripts/run_isolated_tests.py",
            "--",
            "-q",
            "tests/test_migration_reconciliation.py",
            "tests/test_startup_schema_idempotency.py",
        ],
        cwd=API,
        env=env,
    )

    current = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    heads = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=API,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    head_lines = [line.split()[0] for line in heads.stdout.splitlines() if line.strip()]
    if len(head_lines) != 1 or head_lines[0] not in current.stdout:
        raise RuntimeError("Local DEV database is not at the single Alembic head")
    schema_head = head_lines[0]

    engine = create_engine(env["SYNC_DATABASE_URL"])
    required_columns = {
        ("channel_listings", "listing_url"),
        ("channel_listings", "last_payload_hash"),
        ("channel_listings", "last_checked_at"),
        ("browser_listing_jobs", "attempt_count"),
        ("browser_listing_jobs", "available_at"),
    }
    with engine.connect() as connection:
        found = set(
            connection.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND ((table_name, column_name) IN "
                    "(('channel_listings','listing_url'),"
                    "('channel_listings','last_payload_hash'),"
                    "('channel_listings','last_checked_at'),"
                    "('browser_listing_jobs','attempt_count'),"
                    "('browser_listing_jobs','available_at')))"
                )
            ).all()
        )
        if not required_columns.issubset(found):
            raise RuntimeError(f"Local DEV schema is missing columns: {sorted(required_columns - found)}")
        newsletter = connection.execute(
            text("SELECT to_regclass('public.newsletter_subscriptions')")
        ).scalar_one()
        if newsletter is None:
            raise RuntimeError("Local DEV schema is missing newsletter_subscriptions")
    engine.dispose()

    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()
    migration_hashes = {}
    for path in sorted((API / "alembic" / "versions").glob("*.py")):
        if path.name == "__init__.py":
            continue
        relative = path.relative_to(ROOT).as_posix()
        source = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        migration_hashes[relative] = hashlib.sha256(source).hexdigest()
    manifest = {
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "schema_head": schema_head,
        "migration_sha256": migration_hashes,
        "validation": {
            "alembic_upgrade": "passed",
            "isolated_migration_tests": "passed",
            "local_schema_check": "passed",
        },
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Local DEV schema validated at {schema_head}; attestation written to {MANIFEST}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Local DEV schema validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
