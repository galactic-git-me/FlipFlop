from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Build,
    BuildStatus,
    BuildType,
    Customer,
    CustomerProblem,
    EmailEvent,
    ManualBuild,
    Order,
    OrderStatus,
    ShipmentTrackingEvent,
    WarrantyClaim,
    WarrantyReserve,
)
from app.services import email_monitor as email_monitor_module
from app.services import parcel2go_notifications as tracking_notifications
from app.services.email_monitor import EmailMonitor


def test_delivery_email_timestamp_uses_only_explicit_non_future_timezone_value():
    fallback = datetime(2026, 9, 29, 15, 0, 0)
    parsed = EmailMonitor._delivery_timestamp(
        "Parcel delivered at 2026-09-29T14:15:00+01:00",
        fallback=fallback,
    )
    assert parsed == datetime(2026, 9, 29, 13, 15, 0)
    assert EmailMonitor._delivery_timestamp(
        "Parcel delivered at 2026-09-29T16:15:00+01:00",
        fallback=fallback,
    ) == fallback
    assert EmailMonitor._delivery_timestamp(
        "Parcel delivered at 2026-09-29T14:15:00",
        fallback=fallback,
    ) == fallback


@pytest.mark.asyncio
async def test_delivery_email_starts_order_warranty_and_attaches_pre_delivery_claim(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(email_monitor_module, "emit_alert", AsyncMock())
    monkeypatch.setattr(
        tracking_notifications,
        "deliver_tracking_event_notification",
        AsyncMock(return_value={"status": "sent"}),
    )

    async with session_factory() as db:
        original_delivery = datetime(2026, 9, 20, 12, 0, 0)
        customer = Customer(name="Direct Warranty Buyer", email="warranty@example.test")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id="FF-EMAIL-DELIVERY-WARRANTY",
            customer_id=customer.id,
            specs={},
            customer_price=1200,
            component_costs=900,
            overhead_amount=75,
            status=OrderStatus.SHIPPED,
            delivered_at=original_delivery,
            actual_delivery_date=original_delivery,
        )
        build_record = ManualBuild(
            name="Email Warranty Build",
            status="sold",
            customer_id=customer.id,
            tracking_number="TRACK-EMAIL-WARRANTY-1",
            sale_price_actual=1200,
            delivered_at=original_delivery,
            warranty_started_at=original_delivery,
        )
        db.add_all([order, build_record])
        await db.flush()
        db.add(Build(
            build_type=BuildType.PREBUILT,
            order_id=order.id,
            manual_build_id=build_record.id,
            spec_json={},
            status=BuildStatus.FINALISED,
        ))
        pre_delivery_case = CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty",
            description="The customer reported a fault before courier delivery was confirmed.",
        )
        db.add(pre_delivery_case)
        await db.flush()
        build_id = build_record.id
        order_id = order.id
        case_id = pre_delivery_case.id
        await db.commit()

        monitor = EmailMonitor()
        response = await monitor.process_message({
            "msg_id": "delivery-email-warranty-1",
            "subject": "Your parcel has been delivered",
            "sender": "Carrier <updates@example.test>",
            "body": "Delivery confirmed for tracking TRACK-EMAIL-WARRANTY-1.",
        }, db)
        assert response is None
        # A separate repeat notice must reuse the same reserve and delivery date.
        await monitor.process_message({
            "msg_id": "delivery-email-warranty-2",
            "subject": "Your parcel has been delivered",
            "sender": "Carrier <updates@example.test>",
            "body": "Delivery confirmed for tracking TRACK-EMAIL-WARRANTY-1.",
        }, db)

        order = await db.get(Order, order_id)
        build_record = await db.get(ManualBuild, build_id)
        order_reserve = (await db.execute(
            select(WarrantyReserve).where(WarrantyReserve.order_id == order_id)
        )).scalar_one()
        build_reserve = (await db.execute(
            select(WarrantyReserve).where(WarrantyReserve.manual_build_id == build_id)
        )).scalar_one_or_none()
        attached_claim = (await db.execute(
            select(WarrantyClaim).where(WarrantyClaim.customer_problem_id == case_id)
        )).scalar_one()

        assert order.status == OrderStatus.COMPLETED
        assert order.delivered_at == original_delivery
        assert order.actual_delivery_date == order.delivered_at
        assert build_record.warranty_started_at == order.delivered_at
        assert order_reserve.warranty_started_at == order.delivered_at
        assert order_reserve.reserve_pct == 5
        assert build_reserve is None
        assert attached_claim.reserve_id == order_reserve.id
        assert await db.scalar(select(func.count()).select_from(WarrantyReserve)) == 1
        timeline_event = (await db.execute(
            select(ShipmentTrackingEvent).where(
                ShipmentTrackingEvent.provider == "email_monitor",
                ShipmentTrackingEvent.order_id == order_id,
            )
        )).scalar_one()
        assert timeline_event.status_code == "delivered"
        assert timeline_event.customer_notified_at is None
        assert tracking_notifications.deliver_tracking_event_notification.await_count == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_delivery_email_with_ambiguous_order_ownership_creates_no_warranty_reserve(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(email_monitor_module, "emit_alert", AsyncMock())
    monkeypatch.setattr(
        tracking_notifications,
        "deliver_tracking_event_notification",
        AsyncMock(return_value={"status": "not_customer_visible"}),
    )

    async with session_factory() as db:
        customer = Customer(name="Ambiguous Buyer", email="ambiguous@example.test")
        db.add(customer)
        await db.flush()
        orders = [
            Order(
                order_id=f"FF-AMBIGUOUS-{index}",
                customer_id=customer.id,
                specs={},
                customer_price=1000,
                component_costs=700,
                overhead_amount=50,
                status=OrderStatus.SHIPPED,
            )
            for index in (1, 2)
        ]
        build_record = ManualBuild(
            name="Ambiguous Ownership Build",
            status="sold",
            tracking_number="TRACK-AMBIGUOUS-1",
        )
        db.add_all([*orders, build_record])
        await db.flush()
        db.add_all([
            Build(
                build_type=BuildType.PREBUILT,
                order_id=order.id,
                manual_build_id=build_record.id,
                spec_json={},
                status=BuildStatus.FINALISED,
            )
            for order in orders
        ])
        await db.commit()

        monitor = EmailMonitor()
        await monitor.process_message({
            "msg_id": "delivery-email-ambiguous-1",
            "subject": "Your parcel has been delivered",
            "sender": "Carrier <updates@example.test>",
            "body": "Delivery confirmed for tracking TRACK-AMBIGUOUS-1.",
        }, db)

        event = (await db.execute(
            select(EmailEvent).where(EmailEvent.message_id == "delivery-email-ambiguous-1")
        )).scalar_one()
        assert event.manual_build_id == build_record.id
        assert "multiple linked orders" in event.summary
        assert await db.scalar(select(func.count()).select_from(WarrantyReserve)) == 0
        timeline_event = (await db.execute(
            select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.provider == "email_monitor")
        )).scalar_one()
        assert timeline_event.manual_build_id == build_record.id
        assert timeline_event.material is False

    await engine.dispose()


@pytest.mark.asyncio
async def test_indirect_sale_email_does_not_create_or_attach_customer_account():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        existing_customer = Customer(
            name="Existing Account Holder",
            email="buyer@example.test",
            password_hash="already-hashed",
        )
        build = ManualBuild(
            name="FlipFlop Gaming Build",
            status="listed",
            ebay_sku="FF-EBAY-1",
        )
        db.add_all([existing_customer, build])
        await db.flush()
        customer_id = existing_customer.id
        build_id = build.id

        matched = await EmailMonitor()._match_manual_build_sale({
            "marketplace": "ebay",
            "title": "FlipFlop Gaming Build",
            "price": 850,
            "customer_email": "Buyer@Example.Test",
            "customer_name": "Marketplace Buyer",
        }, db)

        saved_build = await db.get(ManualBuild, build_id)
        assert matched is saved_build
        assert saved_build.status == "sold"
        assert saved_build.customer_id is None
        assert saved_build.customer_email == "buyer@example.test"
        assert saved_build.buyer_name == "Marketplace Buyer"
        assert await db.scalar(select(func.count()).select_from(Customer)) == 1
        assert await db.get(Customer, customer_id) is existing_customer

    await engine.dispose()


@pytest.mark.asyncio
async def test_marketplace_sale_without_parsed_price_does_not_use_listing_price():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        build = ManualBuild(name="FlipFlop Gaming Build", status="listed", ebay_price=900)
        db.add(build)
        await db.flush()
        build_id = build.id

        await EmailMonitor()._match_manual_build_sale({
            "marketplace": "ebay",
            "title": "FlipFlop Gaming Build",
            "price": None,
        }, db)

        saved_build = await db.get(ManualBuild, build_id)
        assert saved_build.sale_price_actual is None
        assert saved_build.ebay_price == 900

    await engine.dispose()
