from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


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
