"""Offline regression checks; no database, workers, or providers are started."""
import ast
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "flipflop-api/alembic/versions/20261104_0001_sold_observation_url_text.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourcingBackendContracts(unittest.TestCase):
    def test_sold_url_column_accepts_full_tracking_urls(self):
        class TestBase(DeclarativeBase):
            pass

        database = types.ModuleType("app.database")
        database.Base = TestBase
        with patch.dict(sys.modules, {"app.database": database}):
            module = load_module(
                "sold_url_model",
                ROOT / "flipflop-api/app/models/gem_radar_sold_observation.py",
            )
        model = module.GemRadarSoldObservation
        column = model.__table__.c.source_url
        self.assertEqual(column.type.compile(dialect=postgresql.dialect()), "TEXT")
        url = "https://www.ebay.co.uk/itm/123456789012?tracking=" + "x" * 1500
        self.assertEqual(model(source_url=url).source_url, url)

    def test_migration_widens_url_without_truncating_existing_evidence(self):
        migration = load_module("sold_url_migration", MIGRATION)
        output = io.StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
        with Operations.context(context):
            migration.upgrade()
        sql = output.getvalue()
        self.assertIn("ALTER COLUMN source_url TYPE TEXT", sql)
        self.assertNotIn("DROP", sql.upper())
        self.assertNotIn("SUBSTR", sql.upper())

    def test_production_services_share_available_model_default(self):
        compose = (ROOT / "deploy/andromeda-api.compose.yml").read_text()
        models = re.findall(r"^\s+(?:OLLAMA_MODEL|LLM_PRIMARY_MODEL):\s*(.+)$", compose, re.M)
        self.assertEqual(models, ["${FLIPFLOP_OLLAMA_MODEL:-qwen3:4b}"] * 4)

    def test_migration_extends_the_dev_chain_without_an_extra_head(self):
        # Inspect revision metadata without importing historical migrations
        # that may import application services or require runtime settings.
        revisions = {}
        for path in (ROOT / "flipflop-api/alembic/versions").glob("*.py"):
            metadata = {}
            for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                else:
                    continue
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in ("revision", "down_revision"):
                        metadata[target.id] = ast.literal_eval(node.value)
            if metadata.get("revision"):
                revisions[metadata["revision"]] = metadata.get("down_revision")
        parents = set()
        for parent in revisions.values():
            parents.update(parent if isinstance(parent, tuple) else [parent] if parent else [])
        self.assertFalse(parents - revisions.keys(), "Missing parent migrations")
        self.assertEqual(len(set(revisions) - parents), 1, "Multiple migration heads")
        self.assertEqual(revisions["20261104_0001"], "20261103_0002")


if __name__ == "__main__":
    unittest.main()
