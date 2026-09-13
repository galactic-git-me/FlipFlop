"""Complete daily production -> local PostgreSQL refresh. Never writes production.

Run with flipflop-api/.venv/Scripts/python.exe scripts/refresh-local-database.py.
Requires PostgreSQL 18 client tools and the existing `andromeda` SSH alias.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "flipflop-api"
sys.path.insert(0, str(API))
os.chdir(API)
from app.config import get_settings
from sqlalchemy.engine import make_url

PG = Path("C:/Program Files/PostgreSQL/18/bin")
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
BACKUP = Path(os.environ["LOCALAPPDATA"]) / "FlipFlop" / "database-backups" / STAMP


def run(args, **kwargs):
    # Capture stderr: never echo commands/environment containing credentials.
    return subprocess.run(args, check=True, stderr=subprocess.PIPE, **kwargs)


def main():
    settings = get_settings()
    url = make_url(os.environ.get("DATABASE_URL", settings.database_url))
    if url.host not in {"localhost", "127.0.0.1"} or url.port != 5432 or url.database != "pcflipper":
        raise RuntimeError("Destination must be local pcflipper on loopback port 5432")
    if not (PG / "pg_restore.exe").exists():
        raise RuntimeError("PostgreSQL 18 tools are required")
    local_config = dotenv_values(API / '.env.local')
    admin_user = local_config.get('LOCAL_POSTGRES_ADMIN_USER') or url.username
    admin_password = local_config.get('LOCAL_POSTGRES_ADMIN_PASSWORD') or url.password
    conn_args = dict(host=url.host, port=url.port, user=admin_user, password=admin_password)
    admin = psycopg2.connect(dbname="postgres", **conn_args)
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')
    if not cur.fetchone()[0]:
        raise RuntimeError('Set LOCAL_POSTGRES_ADMIN_USER and LOCAL_POSTGRES_ADMIN_PASSWORD in flipflop-api/.env.local; the full snapshot requires local administrator privileges')
    cur.execute("SELECT pg_try_advisory_lock(739421855)")
    if not cur.fetchone()[0]:
        raise RuntimeError("Another production-to-local refresh is running")
    BACKUP.mkdir(parents=True, exist_ok=False)
    report = {"source": "andromeda/flipflop-production-postgres/pcflipper",
              "destination": "127.0.0.1:5432/pcflipper", "started_at": STAMP,
              "status": "started", "backup_directory": str(BACKUP)}
    report_path = BACKUP / "report.json"
    stage = "pcflipper_stage_" + STAMP.lower()
    env = dict(os.environ, PGPASSWORD=admin_password or "")
    pg_args = ["-h", url.host, "-p", str(url.port), "-U", admin_user]
    paused = False
    try:
        print("Downloading a complete production snapshot...", flush=True)
        with (BACKUP / "production.dump").open("wb") as f:
            run(["ssh", "-o", "BatchMode=yes", "andromeda",
                 "docker exec flipflop-production-postgres pg_dump -U flipper -d pcflipper -Fc --no-owner --no-acl"], stdout=f)
        # These values make encrypted database OAuth tokens usable locally.
        # Capture in memory only; never print secrets or copy unrelated .env settings.
        remote_code = """import json
from app.config import get_settings
s=get_settings()
fields=['ebay_app_id','ebay_client_secret','ebay_ru_name']
d={k.upper():getattr(s,k) for k in fields}
d['EBAY_TOKEN_ENCRYPTION_KEY']=s.ebay_token_encryption_key or s.ebay_client_secret or s.secret_key
print(json.dumps(d))
"""
        result = run(["ssh", "-o", "BatchMode=yes", "andromeda",
                      "docker exec -i flipflop-production-api python -"],
                     input=remote_code.encode(), stdout=subprocess.PIPE)
        ebay_config = json.loads(result.stdout)
        print("Restoring and validating staging database...", flush=True)
        cur.execute(sql.SQL("CREATE DATABASE {} WITH TEMPLATE template0 OWNER {}").format(
            sql.Identifier(stage), sql.Identifier(url.username)))
        run([str(PG / "pg_restore.exe"), *pg_args, "-d", stage, "--no-acl",
             "--exit-on-error", "--single-transaction", str(BACKUP / "production.dump")], env=env)
        with psycopg2.connect(dbname=stage, **conn_args) as staging:
            with staging.cursor() as sc:
                sc.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2")
                tables = sc.fetchall()
                counts = {}
                for schema, table in tables:
                    sc.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table)))
                    counts[f"{schema}.{table}"] = sc.fetchone()[0]
                if not counts.get("public.app_settings") or "public.manual_builds" not in counts:
                    raise RuntimeError("Snapshot is missing required application tables")
                report["table_counts"] = counts
                sc.execute("SELECT ebay_seller_access_token,ebay_seller_refresh_token FROM app_settings WHERE name='default'")
                tokens = sc.fetchone()
                if tokens:
                    import base64, hashlib
                    from cryptography.fernet import Fernet
                    cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(ebay_config['EBAY_TOKEN_ENCRYPTION_KEY'].encode()).digest()))
                    for token in tokens:
                        if token and token.startswith('enc:v1:'):
                            cipher.decrypt(token.removeprefix('enc:v1:').encode())
        print(f"Validated {len(counts)} tables. Pausing local database writers...", flush=True)
        run(["pwsh", "-NoProfile", "-File", str(ROOT / "scripts/local-refresh-services.ps1"), "-Action", "Stop"])
        paused = True
        env_path = API / ".env.local"
        cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (url.database,))
        # DEV is disposable and is being replaced by the validated production
        # snapshot. Do not create a second local dump/database during refresh.
        # PostgreSQL requires DROP DATABASE to run outside a transaction.
        admin.autocommit = True
        cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(url.database)))
        admin.autocommit = False
        try:
            cur.execute(sql.SQL("ALTER DATABASE {} RENAME TO {}").format(sql.Identifier(stage), sql.Identifier(url.database)))
            admin.commit()
        except Exception:
            admin.rollback()
            raise
        finally:
            admin.autocommit = True
        for key, value in ebay_config.items():
            set_key(str(env_path), key, value)
        # Prefer the copied seller connection rather than obsolete static tokens.
        for key in ['EBAY_PRODUCTION_REFRESH_TOKEN', 'EBAY_PRODUCTION_OAUTH_USER_TOKEN']:
            set_key(str(env_path), key, '')
        set_key(str(env_path), 'EBAY_LISTING_ENVIRONMENT', 'production')
        set_key(str(env_path), 'WEB_ONLY', 'true')
        report['status'] = 'complete'
        print(f"Refresh complete. Production snapshot and report: {BACKUP}", flush=True)
    except Exception as exc:
        report['status'] = 'failed'
        report['error_type'] = type(exc).__name__
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        if paused:
            run(["pwsh", "-NoProfile", "-File", str(ROOT / "scripts/local-refresh-services.ps1"), "-Action", "Start"])
        admin.close()


if __name__ == '__main__':
    main()
