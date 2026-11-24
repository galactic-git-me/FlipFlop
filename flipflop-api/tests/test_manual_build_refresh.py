from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_due_active_listing_is_revised_in_place_and_rescheduled():
    from app.workers.manual_build_lifecycle import _recreate_manual_build

    build = SimpleNamespace(
        id=42,
        name="Test PC",
        ebay_listing_id="188805793027",
        ebay_listing_url="https://www.ebay.co.uk/itm/188805793027",
        ebay_sku="FLP-EXISTING1",
        ebay_listing_status="active",
        ebay_listing_status_checked_at=None,
        generated_title="Old title",
        generated_description="Old description",
        generated_aspects={"Brand": ["FlipFlop"], "Type": ["Desktop"]},
        photos=[
            {"url": "https://example.com/one.jpg", "kind": "photo"},
            {"url": "https://example.com/two.jpg", "kind": "photo"},
        ],
        ebay_price=400.0,
        total_cost=300.0,
        sold_comp_target=350.0,
        price_floor=250.0,
        recreate_price_step_pct=5.0,
        price_floor_hit_review_needed=False,
        recreate_cycle_count=0,
    )
    settings_result = MagicMock()
    settings_result.scalar_one_or_none.return_value = SimpleNamespace(
        relist_interval_days=7
    )
    db = MagicMock()
    db.execute = AsyncMock(return_value=settings_result)

    async def reconcile(*_args, **_kwargs):
        build.ebay_listing_status = "active"
        return "active"

    with (
        patch(
            "app.services.ebay_listing_reconciliation.reconcile_manual_build_listing",
            new=AsyncMock(side_effect=reconcile),
        ),
        patch(
            "app.services.ebay_browse.get_component_prices",
            new=AsyncMock(return_value={"used_prices": [350], "new_prices": []}),
        ),
        patch(
            "app.workers.manual_build_lifecycle.pricing_engine.recalculate_manual_build_pricing",
            new=AsyncMock(),
        ),
        patch(
            "app.workers.manual_build_lifecycle.pricing_engine.compute_next_drop_price",
            return_value=(380.0, False),
        ),
        patch(
            "app.api.manual_builds.generate_listing",
            new=AsyncMock(return_value=SimpleNamespace(titles=["New title"])),
        ),
        patch(
            "app.workers.manual_build_lifecycle.post_build_to_ebay",
            new=AsyncMock(return_value="published"),
        ) as publish,
    ):
        outcome = await _recreate_manual_build(build, db)

    assert outcome == "published"
    publish.assert_awaited_once_with(build, db=db, update_existing=True)
    assert build.generated_title == "New title"
    assert build.ebay_price == 380.0
    assert build.photos[0]["url"] == "https://example.com/two.jpg"
    assert build.ebay_listing_id == "188805793027"
    assert build.recreate_cycle_count == 1
    assert build.last_recreate_at is not None
    assert build.next_recreate_at > datetime.utcnow()


@pytest.mark.asyncio
async def test_existing_inventory_listing_uses_saved_sku_for_update():
    from app.workers.manual_build_scheduler import post_build_to_ebay

    build = SimpleNamespace(
        id=42,
        generated_title="Updated title",
        generated_description="Updated description",
        generated_aspects={"Brand": ["FlipFlop"], "Type": ["Desktop"]},
        photos=[{"url": "https://example.com/pc.jpg", "kind": "photo"}],
        ebay_price=380.0,
        ebay_listing_id="188805793027",
        ebay_listing_url="https://www.ebay.co.uk/itm/188805793027",
        ebay_sku="FLP-EXISTING1",
        ebay_condition="USED_EXCELLENT",
        fulfillment_policy_id=None,
        ebay_listing_status="active",
        ebay_listing_status_checked_at=None,
        ebay_listing_end_reason=None,
        updated_at=None,
        promoted_enabled=False,
    )
    settings = SimpleNamespace(
        ebay_listing_environment="sandbox",
        ebay_sandbox_payment_policy_id="pay",
        ebay_sandbox_return_policy_id="return",
        ebay_sandbox_fulfillment_policy_id="ship",
    )
    result = {
        "success": True,
        "listing_id": build.ebay_listing_id,
        "url": build.ebay_listing_url,
        "sku": build.ebay_sku,
    }

    with (
        patch(
            "app.workers.manual_build_scheduler.get_settings",
            return_value=settings,
        ),
        patch(
            "app.services.ebay_token_manager.get_valid_ebay_access_token",
            new=AsyncMock(return_value="sandbox-token"),
        ),
        patch(
            "app.workers.manual_build_scheduler.post_flip_to_ebay",
            new=AsyncMock(return_value=result),
        ) as post,
    ):
        outcome = await post_build_to_ebay(build, update_existing=True)

    assert outcome == "published"
    assert post.await_args.kwargs["listing_id"] == "188805793027"
    assert post.await_args.kwargs["sku"] == "FLP-EXISTING1"
    assert post.await_args.kwargs["environment"] == "sandbox"
