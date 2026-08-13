"""
Row 49: a fast/near-asking sale should bias the *next* similar build's
(same cpu_tier) initial pricing anchor up, not just reset every cycle.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.listing import Listing
from app.models.flip import Flip, FlipStage
from app.models.pricing_bias import PricingBias
from app.services import pricing_engine

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    yield SessionLocal
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    return TestClient(app)


async def _make_listing(session_factory, cpu="i7-13700K") -> int:
    async with session_factory() as session:
        listing = Listing(
            external_id=f"bias-{uuid.uuid4()}", source_id=1, title="Gaming PC",
            price=800.0, url="https://example.com", source_name="eBay UK", cpu=cpu,
        )
        session.add(listing)
        await session.flush()
        await session.commit()
        return listing.id


async def test_fast_sale_creates_pricing_bias_row(client, test_db):
    listing_id = await _make_listing(test_db, cpu="i7-13700K")
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    client.patch(f"/api/flips/{flip_id}", json={"listing_price": 1000.0})

    resp = client.post(f"/api/flips/{flip_id}/sold", json={"actual_sale_price": 990.0, "sale_platform": "eBay"})
    assert resp.status_code == 200

    async with test_db() as db:
        bias = await db.get(PricingBias, "i7")
        assert bias is not None
        assert bias.anchor_bias_pct > 0
        assert bias.triggered_by_flip_id == flip_id


async def test_slow_sale_does_not_create_bias(client, test_db):
    listing_id = await _make_listing(test_db, cpu="i5-12400")
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    client.patch(f"/api/flips/{flip_id}", json={"listing_price": 1000.0})

    # Backdate created_at so days_to_sell is large (slow sale).
    async with test_db() as db:
        flip = await db.get(Flip, flip_id)
        from datetime import datetime, timedelta
        flip.created_at = datetime.utcnow() - timedelta(days=30)
        await db.commit()

    resp = client.post(f"/api/flips/{flip_id}/sold", json={"actual_sale_price": 600.0, "sale_platform": "eBay"})
    assert resp.status_code == 200

    async with test_db() as db:
        bias = await db.get(PricingBias, "i5")
        assert bias is None


async def test_recalculate_pricing_applies_existing_bias(test_db):
    from unittest.mock import AsyncMock, patch

    async with test_db() as db:
        db.add(PricingBias(cpu_tier="i7", anchor_bias_pct=0.05, triggered_by_flip_id=1))
        listing = Listing(
            external_id=f"bias2-{uuid.uuid4()}", source_id=1, title="Gaming PC",
            price=800.0, url="https://example.com", source_name="eBay UK", cpu="i7-13700K",
        )
        db.add(listing)
        await db.flush()
        flip = Flip(listing_id=listing.id, stage=FlipStage.selected, total_cost=800.0, offers_enabled=False)
        db.add(flip)
        await db.commit()

        fake_prices = {
            "new_prices": [], "new_cheapest": None,
            "used_prices": [900.0, 950.0, 1000.0], "used_cheapest": None,
            "used_median": 950.0, "new_min": None,
        }
        with patch("app.services.ebay_browse.get_component_prices", new=AsyncMock(return_value=fake_prices)):
            result = await pricing_engine.recalculate_pricing(flip, db)

    # offers_enabled=False -> anchor = sold_comp_target (950.0) per compute_bin_anchor,
    # then biased up 5% by the stored PricingBias row for cpu_tier "i7".
    assert result["listing_price"] == round(950.0 * 1.05, 2)
