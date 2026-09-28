"""The admin work queue classifies paid orders from persisted order data."""
from datetime import datetime, timedelta

import pytest

from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.models.product import Product, ProductStatus, ProductType
from app.routes.admin import list_order_priority


@pytest.mark.asyncio
async def test_active_orders_prioritise_prebuilt_fast_track_then_normal(db):
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
    completed = Order(
        order_id="completed", customer_id=customer.id, specs={}, customer_price=800,
        component_costs=400, overhead_amount=100,
        status=OrderStatus.COMPLETED, created_at=now - timedelta(days=4),
    )
    db.add_all([normal, fast, prebuilt, completed])
    await db.flush()
    db.add(Product(
        product_type=ProductType.PREBUILT, status=ProductStatus.SOLD,
        sold_order_id=prebuilt.id, fulfilment_type="prebuilt",
    ))
    await db.flush()

    result = await list_order_priority(status=None, skip=0, limit=50, db=db)

    assert result["total"] == 3
    assert [order["order_id"] for order in result["orders"]] == ["prebuilt", "fast", "normal"]
    assert [order["priority_kind"] for order in result["orders"]] == ["prebuilt", "fast_track", "normal"]
