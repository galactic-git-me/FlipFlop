from logging.config import fileConfig
from sqlalchemy import inspect, pool, engine_from_config
from sqlalchemy.engine import Connection
from alembic import context
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base
from app.config import get_settings
import app.models  # noqa: F401 — registers all models

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.sync_database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    existing_tables = set(inspect(connection).get_table_names())
    # Inspection autobegins a SQLAlchemy transaction. Alembic treats an
    # already-open transaction as externally managed, so close this read-only
    # inspection transaction before letting Alembic own the migration one.
    if connection.in_transaction():
        connection.commit()
    bootstrap_empty_database = existing_tables.issubset({"flipflop_test_run_marker"})
    if bootstrap_empty_database:
        # The migration chain starts from a pre-Alembic application schema.
        # Create that canonical current schema for a clean install, then let
        # historical revisions add migration-owned tables/columns safely.
        Base.metadata.create_all(connection)
        # SQLAlchemy 2 starts an implicit transaction for create_all(). Commit
        # the empty-schema baseline before Alembic configures its own migration
        # transaction; otherwise connection close rolls the entire chain back.
        connection.commit()

    context.configure(connection=connection, target_metadata=target_metadata)
    reconcile_existing = (
        bootstrap_empty_database
        or context.get_x_argument(as_dictionary=True).get("reconcile_existing") == "true"
    )
    if reconcile_existing:
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("reconcile_existing", os.path.join(os.path.dirname(__file__), "reconcile_existing.py"))
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        module.install_reconciliation(
            context.get_context(),
            empty_baseline=bootstrap_empty_database,
        )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
