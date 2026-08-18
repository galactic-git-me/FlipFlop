"""SSH-transported, allow-listed production catalogue snapshots.

This deliberately excludes customers, orders, payments, worker queues and all
Gem Radar telemetry. SSH authenticates the transport; the importer accepts
only the fixed table list below and performs primary-key upserts.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime
from enum import Enum
import json
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings


TABLES = (
    "playbooks",
    "playbook_slots",
    "listings",
    "catalogue_variants",
    "configurator_catalogue_visibility",
    "case_catalogue",
    "component_3d_assets",
    "manual_builds",
    "builds",
    "capture_3d_assets",
    "cx_documents",
    "products",
)

# Operational references that are intentionally not replicated to production.
NULL_COLUMNS = {
    "configurator_catalogue_visibility": {"updated_by"},
    "builds": {"flip_id", "order_id", "pcbuild_id"},
    "capture_3d_assets": {"order_id"},
    "cx_documents": {"order_id", "template_id"},
    "products": {"sold_order_id", "profit_calculation_id"},
}


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported snapshot value: {type(value)!r}")


def _object_hook(value):
    marker = value.get("__datetime__")
    if marker:
        return datetime.fromisoformat(marker)
    return value


def _engine():
    return create_engine(get_settings().sync_database_url)


def export_snapshot(path: Path) -> None:
    engine = _engine()
    metadata = MetaData()
    payload = {"version": 1, "tables": {}}
    with engine.connect() as connection:
        for name in TABLES:
            table = Table(name, metadata, autoload_with=engine)
            rows = [dict(row) for row in connection.execute(select(table)).mappings()]
            for row in rows:
                for column in NULL_COLUMNS.get(name, set()):
                    if column in row:
                        row[column] = None
            payload["tables"][name] = rows
    path.write_text(json.dumps(payload, default=_json_default), encoding="utf-8")
    engine.dispose()


def import_snapshot(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"), object_hook=_object_hook)
    if payload.get("version") != 1 or set(payload.get("tables", {})) - set(TABLES):
        raise ValueError("Unsupported or unsafe production snapshot")

    engine = _engine()
    metadata = MetaData()
    with engine.begin() as connection:
        for name in TABLES:
            rows = payload["tables"].get(name, [])
            if not rows:
                continue
            table = Table(name, metadata, autoload_with=engine)
            valid_columns = {column.name for column in table.columns}
            rows = [{key: value for key, value in row.items() if key in valid_columns} for row in rows]
            primary_keys = [column.name for column in table.primary_key.columns]
            for offset in range(0, len(rows), 250):
                statement = insert(table).values(rows[offset:offset + 250])
                update_columns = {
                    column.name: statement.excluded[column.name]
                    for column in table.columns
                    if column.name not in primary_keys
                }
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=primary_keys,
                        set_=update_columns,
                    )
                )
            if len(primary_keys) == 1 and primary_keys[0] == "id":
                connection.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {name}), 1), true)"
                    )
                )
    engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("export", "import"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.operation == "export":
        export_snapshot(args.path)
    else:
        import_snapshot(args.path)


if __name__ == "__main__":
    main()
