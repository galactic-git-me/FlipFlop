from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.models.product import (
    ListingChannel,
    Product,
    ProductListing,
    ProductListingStatus,
    ProductStatus,
    ProductType,
    WithdrawalReason,
)
from app.routes.admin_auth import get_current_admin


@pytest.fixture
async def test_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    async def override_current_admin():
        return None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = override_current_admin
    yield session_factory
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_admin, None)
    await engine.dispose()


@pytest.fixture
def client(test_db):
    return TestClient(app)


async def _create_listing(session_factory, *, status=ProductStatus.LISTED, reserved_until=None):
    async with session_factory() as session:
        product = Product(product_type=ProductType.PREBUILT, status=status, reserved_until=reserved_until)
        session.add(product)
        await session.flush()
        build = ManualBuild(name="Test PC", status="listed", storefront_product_id=product.id)
        session.add(build)
        await session.flush()
        session.add_all([
            ProductListing(product_id=product.id, channel=ListingChannel.STOREFRONT, status=ProductListingStatus.ACTIVE),
            ChannelListing(manual_build_id=build.id, channel="flipflop_shop", status="published", recreate_enabled=True),
            ChannelListing(manual_build_id=build.id, channel="ebay_uk", status="published", recreate_enabled=True),
        ])
        await session.commit()
        return build.id, product.id


@pytest.mark.asyncio
async def test_withdraw_storefront_preserves_other_channels_and_audits_reason(client, test_db):
    build_id, product_id = await _create_listing(test_db)

    response = client.post(
        f"/api/manual-builds/{build_id}/withdraw-storefront",
        json={"reason": "Unpublished by admin from Live Builds"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    async with test_db() as session:
        product = await session.get(Product, product_id)
        product_listing = (await session.execute(select(ProductListing).where(ProductListing.product_id == product_id))).scalar_one()
        channels = (await session.execute(select(ChannelListing).where(ChannelListing.manual_build_id == build_id))).scalars().all()
        event = (await session.execute(select(ListingPublishEvent))).scalar_one()
    assert product.status == ProductStatus.WITHDRAWN
    assert product_listing.status == ProductListingStatus.WITHDRAWN
    assert product_listing.withdrawal_reason == WithdrawalReason.MANUAL
    storefront = next(row for row in channels if row.channel == "flipflop_shop")
    ebay = next(row for row in channels if row.channel == "ebay_uk")
    assert storefront.status == "withdrawn"
    assert storefront.recreate_enabled is False
    assert storefront.next_recreate_at is None
    assert ebay.status == "published"
    assert ebay.recreate_enabled is True
    assert event.event_type == "withdrawn"
    assert event.message == "Unpublished by admin from Live Builds"


@pytest.mark.asyncio
async def test_withdraw_storefront_rejects_sold_and_reserved_products(client, test_db):
    sold_build_id, _ = await _create_listing(test_db, status=ProductStatus.SOLD)
    reserved_build_id, _ = await _create_listing(
        test_db,
        status=ProductStatus.RESERVED,
        reserved_until=datetime.utcnow() + timedelta(minutes=5),
    )

    sold_response = client.post(f"/api/manual-builds/{sold_build_id}/withdraw-storefront", json={"reason": "Manual removal"})
    reserved_response = client.post(f"/api/manual-builds/{reserved_build_id}/withdraw-storefront", json={"reason": "Manual removal"})

    assert sold_response.status_code == 409
    assert reserved_response.status_code == 409
