"""Print a compact JSON summary of the local PostgreSQL database."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from sqlalchemy import text

from app.database import engine


async def main() -> None:
    async with engine.connect() as connection:
        tables = (
            await connection.execute(
                text("""
                    SELECT schemaname, tablename
                    FROM pg_tables
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                """)
            )
        ).all()
        total = 0
        latest = None
        for schema, table in tables:
            qualified = f'"{schema.replace(chr(34), chr(34) * 2)}"."{table.replace(chr(34), chr(34) * 2)}"'
            total += int((await connection.execute(text(f"SELECT count(*) FROM {qualified}"))).scalar_one())
            columns = (
                await connection.execute(
                    text("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = :schema AND table_name = :table
                          AND column_name IN ('updated_at','created_at','last_updated','observed_at','completed_at')
                    """),
                    {"schema": schema, "table": table},
                )
            ).scalars().all()
            for column in columns:
                value = (await connection.execute(text(f"SELECT max(\"{column}\") FROM {qualified}"))).scalar_one_or_none()
                if isinstance(value, str):
                    try:
                        value = datetime.fromisoformat(value)
                    except ValueError:
                        continue
                if value is not None and (latest is None or value > latest):
                    latest = value
    print(json.dumps({"total_rows": total, "last_updated": latest.isoformat() if latest else None}))
    await engine.dispose()


asyncio.run(main())
