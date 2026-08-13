#!/usr/bin/env python
"""
PostgreSQL connection cleanup script.
Terminates idle and stale connections to prevent pool exhaustion.
Can be run manually or scheduled via cron/Windows Task Scheduler.
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Load .env file
from dotenv import load_dotenv
env_file = Path(__file__).parent / ".env"
load_dotenv(env_file)

async def cleanup_connections():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://flipper:flipper@127.0.0.1:5432/pcflipper"
    )

    engine = create_async_engine(database_url, echo=False)

    try:
        async with engine.begin() as conn:
            # Terminate idle connections older than 5 minutes
            print(f"[{datetime.now()}] Starting database connection cleanup...")

            result = await conn.execute(text("""
                SELECT pid, usename, application_name, state, state_change
                FROM pg_stat_activity
                WHERE state = 'idle'
                AND state_change < NOW() - INTERVAL '5 minutes'
                AND pid != pg_backend_pid()
            """))

            idle_conns = result.fetchall()
            print(f"Found {len(idle_conns)} idle connections older than 5 minutes")

            for row in idle_conns:
                pid, usename, app_name, state, state_change = row
                print(f"  Terminating PID {pid} ({app_name or 'unknown'}) idle since {state_change}")

                try:
                    await conn.execute(text(f"SELECT pg_terminate_backend({pid})"))
                except Exception as e:
                    print(f"  Error terminating PID {pid}: {e}")

            # Show current connection count
            result = await conn.execute(text("""
                SELECT count(*), state FROM pg_stat_activity
                GROUP BY state
            """))

            print("\nCurrent connection state after cleanup:")
            for count, state in result.fetchall():
                print(f"  {state}: {count}")

            print(f"[{datetime.now()}] Cleanup complete")

    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(cleanup_connections())
