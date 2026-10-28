from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api import assets_admin
from app.api.public_configurator import _variant_asset_is_publishable
from app.models.component_3d_asset import Component3DAssetStatus


def _variant(**overrides):
    values = {
        "status": "active",
        "asset_media_review": {"status": "approved", "image_urls": ["https://media.test/a.jpg"]},
    }
    return SimpleNamespace(**(values | overrides))


def _asset(**overrides):
    values = {
        "category": "case",
        "is_active": True,
        "status": Component3DAssetStatus.FINAL,
        "glb_ref": "https://media.test/model.glb",
        "source_image_refs": ["https://media.test/a.jpg"],
    }
    return SimpleNamespace(**(values | overrides))


def test_exact_final_model_from_approved_photos_is_publishable():
    assert _variant_asset_is_publishable(_variant(), _asset())


def test_component_without_approved_photos_is_not_publishable():
    assert not _variant_asset_is_publishable(
        _variant(asset_media_review={"status": "pending", "image_urls": ["https://media.test/a.jpg"]}),
        _asset(),
    )


def test_unpublished_or_differently_sourced_model_is_not_publishable():
    assert not _variant_asset_is_publishable(_variant(), _asset(status=Component3DAssetStatus.MESHY_DRAFT))
    assert not _variant_asset_is_publishable(_variant(), _asset(source_image_refs=["https://media.test/other.jpg"]))


@pytest.mark.asyncio
async def test_generation_api_rejects_unapproved_photos_before_meshy(monkeypatch):
    variant = SimpleNamespace(asset_media_review=None)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one_or_none=lambda: (variant, SimpleNamespace(slot_type="cpu")))))
    meshy = AsyncMock()
    monkeypatch.setattr(assets_admin, "generate_multi_image_asset", meshy)
    monkeypatch.setattr(assets_admin, "media_members", AsyncMock(return_value=("cpu", "cpu_exact", [variant])))

    with pytest.raises(HTTPException) as error:
        await assets_admin.generate_variant_asset(12, assets_admin.VariantMeshyGenerate(), BackgroundTasks(), SimpleNamespace(email="admin"), db)

    assert error.value.status_code == 409
    meshy.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_api_accepts_job_and_schedules_background_generation(monkeypatch):
    variant = SimpleNamespace(
        id=12,
        listing_id=34,
        asset_media_review={"status": "approved", "model_image_urls": ["https://media.test/a.jpg"]},
    )
    sibling = SimpleNamespace(id=12, asset_media_review=variant.asset_media_review)
    slot = SimpleNamespace(slot_type="case")
    execute = AsyncMock()
    execute.side_effect = [
        SimpleNamespace(one_or_none=lambda: (variant, slot)),
        SimpleNamespace(scalar_one_or_none=lambda: None),
        SimpleNamespace(scalar_one_or_none=lambda: None),
    ]
    db = SimpleNamespace(execute=execute)
    db.commit = AsyncMock()
    monkeypatch.setattr(assets_admin, "media_members", AsyncMock(return_value=("case", "case_exact", [sibling])))
    monkeypatch.setattr(assets_admin, "_run_variant_generation", AsyncMock())
    background_tasks = BackgroundTasks()

    result = await assets_admin.generate_variant_asset(
        12, assets_admin.VariantMeshyGenerate(), background_tasks, SimpleNamespace(email="admin"), db
    )

    assert result["status"] == "accepted"
    assert result["variant_id"] == 12
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is assets_admin._run_variant_generation
    db.commit.assert_awaited_once()


def test_media_pool_prefers_ready_substitutes_without_exposing_blocked_alternatives():
    from app.services.playbook_service import media_candidate_pool
    blocked = {"role": "cpu", "variant_id": 1, "media_ready": False}
    ready = {"role": "cpu", "variant_id": 2, "media_ready": True}
    research = {"role": "ram", "variant_id": 3, "media_ready": False}
    assert media_candidate_pool([blocked, ready, research]) == [ready, research]
    assert media_candidate_pool([blocked]) == [blocked]
