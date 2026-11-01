import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("migration_reconciliation", ROOT / "alembic" / "reconcile_existing.py")
reconciliation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconciliation)


def test_compatible_ddl_is_adopted_without_deleting_data():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE retained (id INTEGER NOT NULL PRIMARY KEY, name VARCHAR(30) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO retained VALUES (1, 'original')")
        context = MigrationContext.configure(connection)
        reconciliation.install_reconciliation(context)
        operations = Operations(context)
        operations.create_table("retained", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(30), nullable=False))
        operations.add_column("retained", sa.Column("name", sa.String(30), nullable=False))
        operations.create_index("ix_retained_name", "retained", ["name"])
        operations.create_index("ix_retained_name", "retained", ["name"])
        assert connection.exec_driver_sql("SELECT name FROM retained").scalar() == "original"


def test_incompatible_existing_column_is_not_silently_adopted():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE retained (value VARCHAR(30))")
        context = MigrationContext.configure(connection)
        reconciliation.install_reconciliation(context)
        with pytest.raises(RuntimeError, match="incompatible type"):
            Operations(context).add_column("retained", sa.Column("value", sa.Integer))


def test_merge_parents_are_independent_heads():
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    parents = script.get_revision("20261012_merge_heads")._normalized_down_revisions
    for parent in parents:
        for other in parents:
            if parent != other:
                ancestors = {revision.revision for revision in script.iterate_revisions(other, "base")}
                assert parent not in ancestors
