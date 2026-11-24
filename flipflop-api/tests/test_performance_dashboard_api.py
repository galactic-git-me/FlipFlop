"""
Admin Performance & Margin dashboard (Algorithm Playbook rows 16, 37, 38) —
store-wide utilities, tested independently of any single build.
"""
import uuid
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.flip import Flip, FlipStage
from app.models.flip_intelligence import FlipIntelligence
from app.models.listing import Listing

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


def test_summary_empty_state(client):
    resp = client.get("/api/admin/performance/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sold_count"] == 0
    assert body["active_count"] == 0
    assert body["sell_through_rate"] is None


async def _seed_sale(test_db, profit: float, roi: float, days_to_sell: int):
    async with test_db() as db:
        listing = Listing(
            external_id=f"perf-{uuid.uuid4()}", source_id=1, title="Gaming PC",
            price=800.0, url="https://example.com", source_name="eBay UK",
        )
        db.add(listing)
        await db.flush()
        flip = Flip(listing_id=listing.id, stage=FlipStage.sold, total_cost=800.0)
        db.add(flip)
        await db.flush()
        intel = FlipIntelligence(
            flip_id=flip.id, source_site="eBay UK", buy_price=800.0,
            total_cost=800.0, sell_price=800.0 + profit, sell_platform="eBay",
            days_to_sell=days_to_sell, profit=profit, roi_pct=roi,
        )
        db.add(intel)
        await db.commit()


@pytest.mark.parametrize("dummy", [None])
async def test_summary_aggregates_sold_flips(client, test_db, dummy):
    await _seed_sale(test_db, profit=100.0, roi=12.5, days_to_sell=5)
    await _seed_sale(test_db, profit=200.0, roi=25.0, days_to_sell=3)

    resp = client.get("/api/admin/performance/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sold_count"] == 2
    assert body["total_profit"] == 300.0
    assert body["avg_margin_pct"] == 18.8  # (12.5 + 25.0) / 2, rounded to 1dp
    assert body["avg_days_to_sell"] == 4.0


def test_keyword_research_returns_shape(client):
    resp = client.get("/api/admin/performance/keyword-research", params={"query": "RTX 4070"})
    assert resp.status_code == 200
    body = resp.json()
    for key in ["query", "sample_titles", "frequent_tokens", "note"]:
        assert key in body
