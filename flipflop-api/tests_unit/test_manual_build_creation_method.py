"""Isolated migration checks against disposable in-memory SQLite; no service/provider."""
import importlib.util
from pathlib import Path
import sys
import unittest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('creation_method_migration',ROOT/'alembic/versions/20261020_0001_manual_build_creation_method.py')
migration=importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

class OriginMigrationChecks(unittest.TestCase):
    def setUp(self):
        self.engine=sa.create_engine('sqlite:///:memory:')
        self.connection=self.engine.connect()
        self.connection.execute(sa.text('CREATE TABLE manual_builds (id INTEGER PRIMARY KEY, name VARCHAR(300))'))
        self.connection.execute(sa.text("INSERT INTO manual_builds (id,name) VALUES (1,'Existing build')"))
    def tearDown(self):
        self.connection.close();self.engine.dispose()
    def upgrade(self):
        with Operations.context(MigrationContext.configure(self.connection)):
            migration.upgrade()
    def test_existing_rows_and_future_inserts_get_manual_default(self):
        self.upgrade()
        self.assertEqual(tuple(self.connection.execute(sa.text('SELECT id,name,creation_method FROM manual_builds')).one()),(1,'Existing build','manual'))
        self.connection.execute(sa.text("INSERT INTO manual_builds (id,name) VALUES (2,'Next build')"))
        self.assertEqual(self.connection.execute(sa.text('SELECT creation_method FROM manual_builds WHERE id=2')).scalar_one(),'manual')
    def test_rerun_preserves_ai_origin(self):
        self.upgrade()
        self.connection.execute(sa.text("UPDATE manual_builds SET creation_method='ai' WHERE id=1"))
        self.upgrade()
        self.assertEqual(self.connection.execute(sa.text('SELECT creation_method FROM manual_builds WHERE id=1')).scalar_one(),'ai')
    def test_incompatible_existing_type_is_rejected(self):
        self.connection.execute(sa.text('ALTER TABLE manual_builds ADD COLUMN creation_method INTEGER'))
        with self.assertRaisesRegex(RuntimeError,'VARCHAR'):
            self.upgrade()
    def test_rollback_cannot_destroy_recorded_origins(self):
        self.upgrade()
        with self.assertRaisesRegex(RuntimeError,'origin history'):
            migration.downgrade()
        self.assertEqual(self.connection.execute(sa.text('SELECT count(*) FROM manual_builds')).scalar_one(),1)

if __name__=='__main__':unittest.main()
