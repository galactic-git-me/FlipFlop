import pytest

from app.api.recommendations import create_envelope
from app.services.performance_envelope import CustomerRequirements


class FakeSession:
    def __init__(self):
        self.saved = None

    def add(self, row):
        self.saved = row

    async def commit(self):
        pass

    async def refresh(self, row):
        row.id = 42


@pytest.mark.asyncio
async def test_envelope_records_inputs_and_version_for_replay():
    db = FakeSession()
    result = await create_envelope(CustomerRequirements(primary_use="gaming", budget_gbp=1100), db)
    assert result["recommendation_session_id"] == 42
    assert db.saved.rules_version == result["envelope_version"]
    assert db.saved.requirements_json["budget_gbp"] == 1100
    assert db.saved.envelope_json["hard_minimums"] == result["hard_minimums"]
