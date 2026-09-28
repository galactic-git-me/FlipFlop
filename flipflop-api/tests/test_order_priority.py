"""The admin work queue classifies paid orders from persisted order data."""
from datetime import datetime, timedelta

import pytest

from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.models.product import Product, ProductStatus, ProductType
from app.routes.admin import list_order_priority


@pytest.mark.asyncio
async def test_active_orders_follow_delivery_buckets_and_spend(db):
    customer = Customer(email="priority@example.test", name="Priority Customer")
    db.add(customer)
    await db.flush()
    now = datetime.utcnow()
    normal = Order(
        order_id="normal", customer_id=customer.id, specs={}, customer_price=1000,
        component_costs=600, overhead_amount=100,
        status=OrderStatus.AWAITING_SOURCING, created_at=now - timedelta(days=3),
    )
    fast = Order(
        order_id="fast", customer_id=customer.id, specs={}, customer_price=1200,
        component_costs=700, overhead_amount=100, fast_track_selected=True,
        status=OrderStatus.AWAITING_SOURCING, created_at=now - timedelta(days=2),
    )
    prebuilt = Order(
        order_id="prebuilt", customer_id=customer.id, specs={"product_id": 1}, customer_price=900,
        component_costs=500, overhead_amount=100, fast_track_selected=True,
        status=OrderStatus.READY_TO_PACKAGE, created_at=now - timedelta(days=1),
    )
    prebuilt_standard = Order(
        order_id="prebuilt-standard", customer_id=customer.id, specs={}, customer_price=5000,
        component_costs=500, overhead_amount=100,
        status=OrderStatus.READY_TO_PACKAGE, created_at=now,
    )
    flexible = Order(
        order_id="flexible", customer_id=customer.id, specs={"delivery_mode": "flexible"}, customer_price=9000,
        component_costs=500, overhead_amount=100,
        status=OrderStatus.AWAITING_SOURCING, created_at=now,
    )
    fast_early = Order(
        order_id="fast-early", customer_id=customer.id,
        specs={"ordered_components": [
            {"expected_arrival_at": (now + timedelta(days=1)).isoformat()},
            {"expected_arrival_at": (now + timedelta(days=3)).isoformat()},
        ]}, customer_price=700, component_costs=500, overhead_amount=100,
        fast_track_selected=True, status=OrderStatus.PARTS_ORDERED, created_at=now,
    )
    fast_late = Order(
        order_id="fast-late", customer_id=customer.id,
        specs={"ordered_components": [
            {"expected_arrival_at": (now + timedelta(days=5)).isoformat()},
        ]}, customer_price=3000, component_costs=500, overhead_amount=100,
        fast_track_selected=True, status=OrderStatus.PARTS_ORDERED, created_at=now,
    )
    completed = Order(
        order_id="completed", customer_id=customer.id, specs={}, customer_price=800,
        component_costs=400, overhead_amount=100,
        status=OrderStatus.COMPLETED, created_at=now - timedelta(days=4),
    )
    db.add_all([normal, fast, fast_early, fast_late, prebuilt, prebuilt_standard, flexible, completed])
    await db.flush()
    db.add(Product(
        product_type=ProductType.PREBUILT, status=ProductStatus.SOLD,
        sold_order_id=prebuilt.id, fulfilment_type="prebuilt",
    ))
    db.add(Product(
        product_type=ProductType.PREBUILT, status=ProductStatus.SOLD,
        sold_order_id=prebuilt_standard.id, fulfilment_type="prebuilt",
    ))
    await db.flush()

    result = await list_order_priority(status=None, skip=0, limit=50, db=db)

    assert result["total"] == 7
    assert [order["order_id"] for order in result["orders"]] == [
        "prebuilt", "prebuilt-standard", "fast-early", "fast-late", "fast", "normal", "flexible",
    ]
    assert [order["priority_rank"] for order in result["orders"]] == [1, 2, 3, 3, 3, 4, 5]
    assert result["orders"][2]["components_ready_at"] == now + timedelta(days=3)
    page = await list_order_priority(status=None, skip=2, limit=2, db=db)
    assert [order["order_id"] for order in page["orders"]] == ["fast-early", "fast-late"]
