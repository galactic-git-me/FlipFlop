"""Inspect or narrowly repair the local ManualBuild schema without sending email.

Default is read-only. --apply runs only the creation_method migration, leaving
Alembic history unchanged when earlier unrelated migrations are still pending.
A later normal upgrade sees the existing compatible column and safely skips it.
"""
import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.config import get_settings
from app.models.manual_build import ManualBuild


def check_query():
    return sa.select(ManualBuild).where(
        ManualBuild.delivered_at.is_not(None),
        ManualBuild.customer_email.is_not(None),
        ManualBuild.delivery_followup_sent_at.is_(None),
    )


def snapshot(connection):
    return connection.execute(sa.text("""
        SELECT count(*), md5(coalesce(string_agg(
            md5((to_jsonb(build)-'creation_method')::text), '' ORDER BY id), ''))
        FROM manual_builds AS build
    """)).one()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true",help="Apply the additive local column repair")
    args=parser.parse_args()
    settings=get_settings()
    url=sa.engine.make_url(settings.sync_database_url)
    async_url=sa.engine.make_url(settings.database_url)
    if url.host not in {"127.0.0.1","localhost","::1"} or url.get_backend_name()!="postgresql":
        raise SystemExit("This repair is restricted to local PostgreSQL")
    if (url.host,url.port,url.database)!=(async_url.host,async_url.port,async_url.database):
        raise SystemExit("Async API and migration database targets differ; no changes applied")
    if settings.app_env != "dev":
        raise SystemExit("This repair is restricted to the DEV environment")
    print(f"Local DEV database: {url.host}:{url.port or 5432}/{url.database}")
    engine=sa.create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(sa.text("SET LOCAL statement_timeout = '30s'"))
            if args.apply:
                connection.execute(sa.text("LOCK TABLE manual_builds IN ACCESS EXCLUSIVE MODE"))
            before=snapshot(connection)
            if args.apply:
                path=ROOT/'alembic/versions/20261020_0001_manual_build_creation_method.py'
                spec=importlib.util.spec_from_file_location('manual_build_origin_migration',path)
                migration=importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                if snapshot(connection)!=before:
                    raise RuntimeError("Existing build data changed unexpectedly; repair rolled back")
                print(f"Existing build data preserved: {before[0]} rows")
            present={column['name'] for column in sa.inspect(connection).get_columns('manual_builds')}
            missing=sorted(set(ManualBuild.__table__.columns.keys())-present)
            print(f"Missing mapped columns: {missing}")
            revisions=connection.execute(sa.text('SELECT version_num FROM alembic_version')).scalars().all()
            print(f"Alembic revision (unchanged): {revisions}")
            if missing:
                raise SystemExit(1)
            result=connection.execute(check_query().limit(1)).first()
            print('Follow-up SELECT: PASS (no worker run and no email sent)')
    finally:
        engine.dispose()


if __name__=='__main__':
    main()
