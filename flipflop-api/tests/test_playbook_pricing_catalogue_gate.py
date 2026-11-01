"""Configurators must price only parts returned by their selected catalogue.

Authored from the pre-test strategy; do not execute until it is approved.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api import public_catalogue
from app.services.playbook_pricing import InvalidBuildError, price_playbook_build


@pytest.mark.asyncio
async def test_custom_catalogue_marks_only_playbook_optional_gpu_slot(monkeypatch):
    slots = [
        {"slot_id": 11, "slot_type": "cpu", "variants_by_tier": {"mid": []}},
        {"slot_id": 12, "slot_type": "gpu", "variants_by_tier": {"mid": []}},
    ]
    monkeypatch.setattr(public_catalogue, "_published_playbook_slots", AsyncMock(return_value=slots))
    monkeypatch.setattr(public_catalogue, "public_list_playbooks", AsyncMock(return_value=[]))
    db = Mock()
    db.get = AsyncMock(return_value=SimpleNamespace(requirements={"gpu_required": False}))

    result = await public_catalogue.public_custom_slots(4, db)

    assert result[0]["is_required"] is True
    assert result[1]["is_required"] is False


@pytest.mark.asyncio
async def test_curated_price_rejects_variant_outside_selected_cell(monkeypatch):
    from app.services import playbook_pricing
    monkeypatch.setattr(
        playbook_pricing,
        "apply_curated_cell_upgrades",
        AsyncMock(side_effect=lambda _db, _playbook_id, _cell_id, selections, _indexes: (selections, [])),
    )
    curated_slots = AsyncMock(return_value=[{
        "slot_id": 11,
        "slot_type": "cpu",
        "variants_by_tier": {"mid": [{"id": 21}]},
    }])
    monkeypatch.setattr(public_catalogue, "public_curated_slots", curated_slots)

    with pytest.raises(InvalidBuildError, match="curated catalogue"):
        await price_playbook_build(
            Mock(),
            playbook_id=4,
            slot_selections={11: 99},
            case_id=2,
            build_mode="curated",
            curated_build_id="FF-GVG-01",
        )

    curated_slots.assert_awaited_once()
    assert curated_slots.await_args.args[0] == 4
    assert curated_slots.await_args.args[2] == "FF-GVG-01"


@pytest.mark.asyncio
async def test_custom_price_rejects_variant_outside_custom_catalogue(monkeypatch):
    custom_slots = AsyncMock(return_value=[{
        "slot_id": 11,
        "slot_type": "cpu",
        "variants_by_tier": {"mid": [{"id": 21}]},
    }])
    monkeypatch.setattr(public_catalogue, "public_custom_slots", custom_slots)
    db = Mock()

    with pytest.raises(InvalidBuildError, match="custom catalogue"):
        await price_playbook_build(
            db,
            playbook_id=4,
            slot_selections={11: 99},
            case_id=2,
            build_mode="custom",
        )

    custom_slots.assert_awaited_once_with(4, db)


@pytest.mark.asyncio
async def test_draft_pricing_can_reprice_a_partial_custom_selection(monkeypatch):
    custom_slots = AsyncMock(return_value=[
        {"slot_id": 11, "slot_type": "cpu", "variants_by_tier": {"mid": [{"id": 21}]}},
        {"slot_id": 12, "slot_type": "gpu", "variants_by_tier": {"mid": [{"id": 22}]}},
    ])
    monkeypatch.setattr(public_catalogue, "public_custom_slots", custom_slots)
    db = Mock()
    db.execute = AsyncMock(side_effect=[
        SimpleNamespace(scalar_one_or_none=lambda: "Gaming"),
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(id=11, slot_type="cpu")])),
        SimpleNamespace(all=lambda: [(
            SimpleNamespace(id=21, slot_id=11, display_price=100.0),
            SimpleNamespace(title="Example CPU"),
        )]),
    ])

    priced = await price_playbook_build(
        db,
        playbook_id=4,
        slot_selections={11: 21},
        case_id=None,
        require_complete=False,
    )

    assert [slot.variant_id for slot in priced.slots] == [21]


@pytest.mark.asyncio
async def test_checkout_pricing_requires_every_custom_configurator_slot(monkeypatch):
    monkeypatch.setattr(public_catalogue, "public_custom_slots", AsyncMock(return_value=[
        {"slot_id": 11, "slot_type": "cpu", "variants_by_tier": {"mid": [{"id": 21}]}},
        {"slot_id": 12, "slot_type": "gpu", "variants_by_tier": {"mid": [{"id": 22}]}},
    ]))

    with pytest.raises(InvalidBuildError, match="Select every component slot"):
        await price_playbook_build(
            Mock(),
            playbook_id=4,
            slot_selections={11: 21},
            case_id=2,
            build_mode="custom",
        )


@pytest.mark.asyncio
async def test_custom_checkout_allows_playbook_optional_gpu_but_keeps_cpu_required(monkeypatch):
    monkeypatch.setattr(public_catalogue, "public_custom_slots", AsyncMock(return_value=[
        {"slot_id": 11, "slot_type": "cpu", "is_required": True, "variants_by_tier": {"mid": [{"id": 21}]}},
        {"slot_id": 12, "slot_type": "gpu", "is_required": False, "variants_by_tier": {"mid": [{"id": 22}]}},
    ]))
    db = Mock()
    db.execute = AsyncMock(side_effect=[
        SimpleNamespace(scalar_one_or_none=lambda: "Business & Office"),
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(id=11, slot_type="cpu")])),
        SimpleNamespace(all=lambda: [(
            SimpleNamespace(id=21, slot_id=11, display_price=180.0),
            SimpleNamespace(title="Office CPU"),
        )]),
    ])

    priced = await price_playbook_build(
        db,
        playbook_id=4,
        slot_selections={11: 21},
        case_id=None,
        build_mode="custom",
    )

    assert [slot.variant_id for slot in priced.slots] == [21]


@pytest.mark.asyncio
async def test_custom_checkout_rejects_missing_required_cpu_with_optional_gpu(monkeypatch):
    monkeypatch.setattr(public_catalogue, "public_custom_slots", AsyncMock(return_value=[
        {"slot_id": 11, "slot_type": "cpu", "is_required": True, "variants_by_tier": {"mid": [{"id": 21}]}},
        {"slot_id": 12, "slot_type": "gpu", "is_required": False, "variants_by_tier": {"mid": [{"id": 22}]}},
    ]))

    with pytest.raises(InvalidBuildError, match="Select every component slot"):
        await price_playbook_build(
            Mock(),
            playbook_id=4,
            slot_selections={12: 22},
            case_id=None,
            build_mode="custom",
        )


@pytest.mark.asyncio
async def test_curated_checkout_keeps_gpu_required_even_if_slot_is_marked_optional(monkeypatch):
    from app.services import playbook_pricing

    monkeypatch.setattr(
        playbook_pricing,
        "apply_curated_cell_upgrades",
        AsyncMock(return_value=({11: 21}, [])),
    )
    monkeypatch.setattr(public_catalogue, "public_curated_slots", AsyncMock(return_value=[
        {"slot_id": 11, "slot_type": "cpu", "variants_by_tier": {"mid": [{"id": 21}]}},
        {"slot_id": 12, "slot_type": "gpu", "is_required": False, "variants_by_tier": {"mid": [{"id": 22}]}},
    ]))

    with pytest.raises(InvalidBuildError, match="Select every component slot"):
        await price_playbook_build(
            Mock(),
            playbook_id=4,
            slot_selections={11: 21},
            case_id=2,
            build_mode="curated",
            curated_build_id="FF-GVG-01",
        )
