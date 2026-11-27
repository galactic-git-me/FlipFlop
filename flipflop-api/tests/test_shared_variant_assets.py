from types import SimpleNamespace

import pytest

from app.models.component_3d_asset import AssetSubjectType
from app.services.shared_variant_assets import final_assets_by_variant


@pytest.mark.asyncio
async def test_pending_playbook_variant_can_resolve_approved_model_without_public_visibility():
    asset = SimpleNamespace(
        id=77,
        subject_type=AssetSubjectType.CATEGORY_GENERIC,
        category="cpu",
        family_key="cpu_amd",
        source_image_refs=[],
    )
    aliases = [
        (1, 11, "AMD Ryzen 5 9600X", "cpu", False),
        (2, 12, "AMD Ryzen 9 9950X", "cpu", False),
    ]

    class Database:
        def __init__(self):
            self.calls = 0

        async def execute(self, _query):
            self.calls += 1
            if self.calls % 2 == 1:
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [asset]))
            return SimpleNamespace(all=lambda: aliases)

    active = SimpleNamespace(id=1, status="active", asset_media_review={})
    pending = SimpleNamespace(id=2, status="pending_review", asset_media_review={})

    public_models = await final_assets_by_variant(Database(), [active, pending])
    assert set(public_models) == {active.id}

    proposal_models = await final_assets_by_variant(
        Database(), [active, pending], allow_pending_review=True
    )
    assert set(proposal_models) == {active.id, pending.id}
    assert proposal_models[pending.id] is asset
