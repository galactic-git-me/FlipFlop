#!/usr/bin/env python3
import os
import sqlite3
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import execute_values, Json

SQLITE_PATH = os.environ.get('SQLITE_PATH', 'pcflipper.db')
PG_URL = os.environ.get('SYNC_DATABASE_URL', 'postgresql://flipper:flipper@127.0.0.1:5432/pcflipper')

IGNORE_TABLES = {'alembic_version'}
BATCH = 1000


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def parse_pg_dsn(url: str) -> dict:
    p = urlparse(url)
    if p.scheme not in {'postgres', 'postgresql'}:
        raise RuntimeError(f'Unsupported postgres URL: {url}')
    return {
        'dbname': (p.path or '/pcflipper').lstrip('/'),
        'user': p.username or 'flipper',
        'password': p.password or 'flipper',
        'host': p.hostname or '127.0.0.1',
        'port': p.port or 5432,
    }


def get_sqlite_tables(sconn):
    cur = sconn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1")
    return [r[0] for r in cur.fetchall() if r[0] not in IGNORE_TABLES]


def get_columns_sqlite(sconn, table):
    cur = sconn.cursor()
    cur.execute(f'PRAGMA table_info({quote_ident(table)})')
    return [r[1] for r in cur.fetchall()]


def table_exists_pg(pcur, table):
    pcur.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema='public' AND table_name=%s
        )
        """,
        (table,),
    )
    return bool(pcur.fetchone()[0])


def get_columns_pg(pcur, table):
    pcur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [r[0] for r in pcur.fetchall()]


def get_boolean_columns_pg(pcur, table):
    pcur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND data_type='boolean'
        """,
        (table,),
    )
    return {r[0] for r in pcur.fetchall()}


def get_varchar_limits_pg(pcur, table):
    pcur.execute(
        """
        SELECT column_name, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
          AND data_type IN ('character varying', 'character')
          AND character_maximum_length IS NOT NULL
        """,
        (table,),
    )
    return {r[0]: int(r[1]) for r in pcur.fetchall()}


def get_column_meta_pg(pcur, table):
    pcur.execute(
        """
        SELECT
          column_name,
          is_nullable,
          data_type,
          udt_name,
          column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    out = {}
    for name, is_nullable, data_type, udt_name, column_default in pcur.fetchall():
        out[name] = {
            "nullable": (str(is_nullable).upper() == "YES"),
            "data_type": data_type,
            "udt_name": udt_name,
            "default": column_default,
        }
    return out


def fallback_value(col_meta: dict):
    dt = (col_meta.get("data_type") or "").lower()
    udt = (col_meta.get("udt_name") or "").lower()
    if dt in {"boolean"}:
        return False
    if dt in {"json", "jsonb"}:
        return {}
    if dt in {"smallint", "integer", "bigint", "real", "double precision", "numeric", "decimal"}:
        return 0
    if "timestamp" in dt or dt == "date":
        return None
    if dt in {"character varying", "character", "text"}:
        return ""
    if udt.endswith("enum"):
        return None
    return None


def reset_sequence_if_needed(pcur, table):
    # For standard serial PK 'id'
    pcur.execute(
        """
        SELECT pg_get_serial_sequence(%s, 'id')
        """,
        (f'public.{table}',),
    )
    seq = pcur.fetchone()[0]
    if not seq:
        return
    pcur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {quote_ident(table)}")
    max_id = pcur.fetchone()[0] or 0
    if max_id > 0:
        pcur.execute("SELECT setval(%s, %s, %s)", (seq, max_id, True))
    else:
        pcur.execute("SELECT setval(%s, %s, %s)", (seq, 1, False))


def main():
    print(f'[migrate] sqlite: {SQLITE_PATH}')
    print(f'[migrate] postgres: {PG_URL}')

    sconn = sqlite3.connect(SQLITE_PATH)
    sconn.row_factory = sqlite3.Row

    pg_dsn = parse_pg_dsn(PG_URL)
    pconn = psycopg2.connect(**pg_dsn)
    pconn.autocommit = False

    try:
        tables = get_sqlite_tables(sconn)
        # Respect known FK dependencies.
        preferred_order = [
            "app_settings",
            "data_sources",
            "search_configs",
            "playbooks",
            "playbook_proposals",
            "listings",
            "parts",
            "flips",
            "price_history",
            "flip_intelligence",
        ]
        ordered = [t for t in preferred_order if t in tables]
        ordered += [t for t in tables if t not in ordered]
        tables = ordered
        print(f'[migrate] tables in sqlite: {len(tables)}')

        with pconn.cursor() as pcur:
            for table in tables:
                if not table_exists_pg(pcur, table):
                    print(f'[skip] {table}: not present in postgres')
                    continue

                s_cols = get_columns_sqlite(sconn, table)
                p_cols = get_columns_pg(pcur, table)
                bool_cols = get_boolean_columns_pg(pcur, table)
                varchar_limits = get_varchar_limits_pg(pcur, table)
                meta = get_column_meta_pg(pcur, table)

                common_cols = [c for c in s_cols if c in p_cols]
                required_missing = [
                    c for c in p_cols
                    if c not in common_cols
                    and not meta[c]["nullable"]
                    and meta[c]["default"] is None
                ]
                cols = common_cols + required_missing
                if not cols:
                    print(f'[skip] {table}: no common columns')
                    continue

                col_sql = ', '.join(quote_ident(c) for c in cols)
                pcur.execute(f'TRUNCATE TABLE {quote_ident(table)} RESTART IDENTITY CASCADE')

                scur = sconn.cursor()
                scur.execute(f'SELECT {col_sql} FROM {quote_ident(table)}')

                inserted = 0
                while True:
                    rows = scur.fetchmany(BATCH)
                    if not rows:
                        break
                    values = []
                    for row in rows:
                        record = []
                        for c in cols:
                            if c in row.keys():
                                v = row[c]
                            else:
                                v = fallback_value(meta.get(c, {}))
                            if c in bool_cols and v is not None:
                                if isinstance(v, (int, float)):
                                    v = bool(v)
                                elif isinstance(v, str):
                                    vv = v.strip().lower()
                                    if vv in {"1", "t", "true", "yes", "y"}:
                                        v = True
                                    elif vv in {"0", "f", "false", "no", "n"}:
                                        v = False
                            if v is None and c in meta and not meta[c]["nullable"]:
                                v = fallback_value(meta[c])
                            if isinstance(v, str) and c in varchar_limits:
                                max_len = varchar_limits[c]
                                if len(v) > max_len:
                                    v = v[:max_len]
                            if isinstance(v, (dict, list)):
                                v = Json(v)
                            record.append(v)
                        values.append(tuple(record))
                    execute_values(
                        pcur,
                        f'INSERT INTO {quote_ident(table)} ({col_sql}) VALUES %s',
                        values,
                        page_size=BATCH,
                    )
                    inserted += len(values)

                reset_sequence_if_needed(pcur, table)
                print(f'[ok] {table}: inserted {inserted}')

        pconn.commit()
        print('[migrate] completed successfully')

    except Exception:
        pconn.rollback()
        raise
    finally:
        sconn.close()
        pconn.close()


if __name__ == '__main__':
    main()
