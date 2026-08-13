"""
Integration tests for the Pricing/Offers automation endpoints added to
app/api/flips.py (Algorithm Playbook rows 8, 10, 19, 20, 21, 33, 45, 49).

Uses an in-memory SQLite DB via dependency override, same pattern as
tests/test_api_integration.py. eBay network calls inside demand_check /
pricing_engine gracefully no-op without credentials (see those modules),
so these tests exercise the full request/response/DB-write path without
needing live eBay access.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.listing import Listing

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    # StaticPool + check_same_thread=False so every connection shares the
    # same in-memory SQLite DB — plain ":memory:" gives each new connection
    # its own empty database otherwise, which is why fixtures and requests
    # would silently write to different DBs without this.
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


@pytest.fixture
async def listing_id(test_db):
    async with test_db() as session:
        listing = Listing(
            external_id="test-listing-1",
            source_id=1,
            title="Gaming PC i7-13700K RTX 4070",
            price=800.0,
            url="https://example.com/listing/1",
            source_name="eBay UK",
            cpu="i7-13700K",
            gpu="RTX 4070",
            ram_gb=32,
            ram_type="DDR5",
            estimated_resale=1100.0,
            estimated_profit=250.0,
        )
        session.add(listing)
        await session.flush()
        await session.commit()
        return listing.id


def test_create_flip_triggers_demand_check_and_pricing(client, listing_id):
    resp = client.post("/api/flips/", json={"listing_id": listing_id})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Demand check ran (no eBay creds in test env -> gracefully null, not an error)
    assert "demand_checked_at" in body
    # Pricing recalculation ran and set a floor from cost basis
    assert body["price_floor"] == round(body["total_cost"] * 1.10, 2)


def test_patch_min_offer_and_offers_enabled(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    resp = client.patch(f"/api/flips/{flip_id}", json={"min_offer_price": 700.0, "offers_enabled": True})
    assert resp.status_code == 200
    assert resp.json()["min_offer_price"] == 700.0
    assert resp.json()["offers_enabled"] is True


def test_counter_offer_rule1_then_rule2_then_stop(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    client.patch(f"/api/flips/{flip_id}", json={"min_offer_price": 700.0, "listing_price": 1000.0})

    r1 = client.post(f"/api/flips/{flip_id}/counter-offer", json={"buyer_offer": 720.0})
    assert r1.status_code == 200
    assert r1.json()["action"] == "counter"
    first_counter = r1.json()["counter_price"]
    assert first_counter == 860.0  # (720+1000)/2

    r2 = client.post(f"/api/flips/{flip_id}/counter-offer", json={"buyer_offer": 800.0})
    assert r2.json()["action"] == "counter"
    assert r2.json()["counter_price"] == first_counter - 5.0

    r3 = client.post(f"/api/flips/{flip_id}/counter-offer", json={"buyer_offer": 800.0})
    assert r3.json()["action"] == "no_further_rounds"


def test_counter_offer_disabled_declines(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    client.patch(f"/api/flips/{flip_id}", json={"offers_enabled": False})
    resp = client.post(f"/api/flips/{flip_id}/counter-offer", json={"buyer_offer": 500.0})
    assert resp.json()["action"] == "decline"


def test_demand_check_endpoint_returns_shape(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    resp = client.post(f"/api/flips/{flip_id}/demand-check")
    assert resp.status_code == 200
    body = resp.json()
    for key in ["query", "active_count", "sold_count_90d", "sold_data_available", "ratio_ok", "note"]:
        assert key in body


def test_recalculate_pricing_endpoint_sets_floor(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    resp = client.post(f"/api/flips/{flip_id}/recalculate-pricing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_floor"] is not None
    assert body["price_floor"] == round(800.0 * 1.10, 2)


def test_pricing_suggestions_endpoint(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    resp = client.get(f"/api/flips/{flip_id}/pricing-suggestions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["shipping"]["shipping_inclusive_price"] > 0
    assert "suggested_ad_rate_pct" in body["promoted_listings"]


def test_upload_video_saves_locally_and_returns_url(client, listing_id):
    # The background eBay-push step uses the real (non-test) DB session by
    # design (see _push_video_to_ebay_background) since background-task work
    # isn't part of the FastAPI dependency-override chain — short-circuit it
    # here so this test only exercises the local-save path.
    from unittest.mock import AsyncMock, patch

    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    with patch("app.api.flips._push_video_to_ebay_background", new=AsyncMock(return_value=None)):
        resp = client.post(
            f"/api/flips/{flip_id}/upload-video",
            files={"file": ("clip.mp4", b"x" * 1000, "video/mp4")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["video_url"].startswith("/uploads/videos/flip-")
    assert body["video_ebay_status"] == "uploaded_local"

    refreshed = client.get(f"/api/flips/{flip_id}").json()
    assert refreshed["generated_video_url"] == body["video_url"]


def test_upload_video_rejects_wrong_type(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    resp = client.post(
        f"/api/flips/{flip_id}/upload-video",
        files={"file": ("clip.txt", b"not a video", "text/plain")},
    )
    assert resp.status_code == 415


def test_upload_video_rejects_empty_file(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    resp = client.post(
        f"/api/flips/{flip_id}/upload-video",
        files={"file": ("clip.mp4", b"", "video/mp4")},
    )
    assert resp.status_code == 422


def test_watcher_offer_plan_not_due_before_listing(client, listing_id):
    flip_id = client.post("/api/flips/", json={"listing_id": listing_id}).json()["id"]
    resp = client.get(f"/api/flips/{flip_id}/watcher-offer-plan")
    assert resp.status_code == 200
    assert resp.json()["should_send"] is False
