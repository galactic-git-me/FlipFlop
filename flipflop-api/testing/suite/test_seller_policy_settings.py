"""
Seller Policies settings (Algorithm Playbook rows 11-15, 43, 44) — global
eBay Business Policy defaults configured once in Settings, not per build.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

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


def test_seller_policy_defaults(client):
    resp = client.get("/api/settings/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["handling_time_days"] == 2
    assert body["returns_accepted"] is True
    assert body["returns_window_days"] == 30
    assert body["free_shipping_enabled"] is True
    assert body["local_pickup_enabled"] is True
    assert body["listing_type_default"] == "FixedPrice"


def test_seller_policy_update_persists(client):
    resp = client.put("/api/settings/", json={"handling_time_days": 3, "free_shipping_enabled": False})
    assert resp.status_code == 200
    assert resp.json()["handling_time_days"] == 3
    assert resp.json()["free_shipping_enabled"] is False

    refetched = client.get("/api/settings/").json()
    assert refetched["handling_time_days"] == 3
    assert refetched["free_shipping_enabled"] is False
