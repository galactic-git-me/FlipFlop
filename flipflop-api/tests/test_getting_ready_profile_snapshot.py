from types import SimpleNamespace

import pytest

from app.models.curated_build_segment import CuratedBuildSegment
from app.models.getting_started_job import GettingStartedJob
from app.models.manual_build import ManualBuild
from app.models.playbook import Playbook
from app.services.curated_build_policy import definitions
from app.services.product_software import software_profile_for_curated_cell_from_db
from app.services.getting_started_jobs import lock_manual_build_then_getting_started_job


@pytest.mark.asyncio
async def test_curated_software_profile_can_be_reloaded_under_lock(db):
    cell = definitions()["builds"][0]
    playbook = Playbook(name=cell["segment"], software_profile=None)
    segment = CuratedBuildSegment(
        customer_type=cell["segment"],
        budget_level=cell["tier"],
        components={},
        bestseller_components={},
        approved_upgrades=[],
        software_profile={
            "recommended_package_ids": ["7zip.7zip"],
            "rationale": "First reviewed profile.",
        },
    )
    db.add_all([playbook, segment])
    await db.flush()

    before = await software_profile_for_curated_cell_from_db(
        db, cell["id"], playbook.name, playbook.software_profile,
    )
    segment.software_profile = {
        "recommended_package_ids": ["Mozilla.Firefox"],
        "rationale": "Updated reviewed profile.",
    }
    await db.flush()
    after = await software_profile_for_curated_cell_from_db(
        db, cell["id"], playbook.name, playbook.software_profile, lock_profile=True,
    )

    assert before["recommended_package_ids"] == ["7zip.7zip"]
    assert after["recommended_package_ids"] == ["Mozilla.Firefox"]


@pytest.mark.asyncio
async def test_getting_ready_writer_locks_build_before_job():
    build = SimpleNamespace(id=17)
    job = SimpleNamespace(manual_build_id=17)

    class Result:
        def __init__(self, row):
            self.row = row

        def scalar_one_or_none(self):
            return self.row

    class RecordingSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            return Result((build, job)[len(self.statements) - 1])

    session = RecordingSession()
    locked_build, locked_job = await lock_manual_build_then_getting_started_job(session, 17)

    entities = [statement.column_descriptions[0]["entity"] for statement in session.statements]
    assert entities == [ManualBuild, GettingStartedJob]
    assert all(statement._for_update_arg is not None for statement in session.statements)
    assert locked_build is build
    assert locked_job is job
