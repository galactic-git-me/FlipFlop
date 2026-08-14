"""
Integration tests for the pricing/offer/recreate-cycle automation ported
from the retired Flip system onto ManualBuild (Algorithm Playbook rows
1, 2, 5, 6, 8, 9, 10, 19, 20, 21, 33, 36, 45, 46, 49).

Same in-memory SQLite pattern as tests/test_flip_automation_api.py, plus a
get_current_admin override since app/api/manual_builds.py's router requires
an admin JWT.
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.database import engine as real_engine
from app.models.manual_build import ManualBuild
from app.routes.admin_auth import get_current_admin

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
async def _dispose_real_engine_pool():
    # Several tests below call worker functions (run_manual_build_offer_poll_job
    # etc.) that open their own session via app.database.AsyncSessionLocal —
    # a real asyncpg pool bound to whichever event loop first used it. Since
    # pytest-asyncio gives each test function a fresh event loop, a pooled
    # connection surviving from a previous test triggers "Future attached to
    # a different loop". Disposing before/after forces fresh connections
    # scoped to *this* test's loop.
    await real_engine.dispose()
    yield
    await real_engine.dispose()


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

    async def override_get_current_admin():
        return None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = override_get_current_admin
    yield SessionLocal
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
def client(test_db):
    return TestClient(app)


async def _built_build(client, SessionLocal, with_offer_floor=200.0):
    build_id = client.post("/api/manual-builds/", json={"name": "Test Build"}).json()["id"]
    async with SessionLocal() as db:
        build = await db.get(ManualBuild, build_id)
        build.components = [
            {"slot": "CPU", "name": "AMD Ryzen 5 5600X", "price_paid": 120, "source": "manual", "purchased": True},
            {"slot": "GPU", "name": "Nvidia RTX 3060", "price_paid": 200, "source": "manual", "purchased": True},
        ]
        build.total_cost = 320.0
        build.auto_reject_below_price = with_offer_floor
        await db.commit()
    return build_id


@pytest.mark.asyncio
async def test_mark_built_fires_demand_check_and_pricing(client, test_db):
    build_id = await _built_build(client, test_db)

    with patch(
        "app.services.demand_check.check_demand",
        new=AsyncMock(return_value=type(
            "S", (), {"sold_count_90d": 12, "active_count": 40, "checked_at": datetime.utcnow()}
        )()),
    ), patch(
        "app.services.ebay_browse.get_component_prices",
        new=AsyncMock(return_value={"used_prices": [300, 310, 320], "new_prices": [], "used_median": 310}),
    ):
        resp = client.post(f"/api/manual-builds/{build_id}/mark-built")

    assert resp.status_code == 200
    body = resp.json()
    assert body["demand_sold_count_90d"] == 12
    assert body["demand_active_count"] == 40
    assert body["price_floor"] == pytest.approx(320.0 * 1.10, abs=0.01)
    assert body["sold_comp_target"] == 310


@pytest.mark.asyncio
async def test_offer_engine_counters_within_tolerance(client, test_db):
    from app.services import offer_engine

    decision = offer_engine.evaluate_buyer_offer(
        buyer_offer=250.0,
        listing_price=320.0,
        min_offer_price=200.0,
        offers_enabled=True,
        counter_offer_round=0,
        last_counter_offer_price=None,
    )
    assert decision.action == "counter"
    assert decision.counter_price == pytest.approx((250.0 + 320.0) / 2, abs=0.01)


async def _real_db_build(**overrides) -> int:
    """
    The worker jobs below (run_manual_build_offer_poll_job etc.) open their
    own session via app.database.AsyncSessionLocal — the real Postgres DB,
    not the in-memory SQLite the `client`/`test_db` fixtures use. So these
    need the build inserted directly into that same real DB, same pattern
    as tests/test_recreate_cycle_job.py.
    """
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        build = ManualBuild(
            name="Real DB Test Build",
            components=[
                {"slot": "CPU", "name": "AMD Ryzen 5 5600X", "price_paid": 120, "source": "manual", "purchased": True},
            ],
            total_cost=320.0,
            auto_reject_below_price=200.0,
            allow_offers=True,
            **overrides,
        )
        db.add(build)
        await db.commit()
        await db.refresh(build)
        return build.id


@pytest.fixture(autouse=True)
async def _clean_real_manual_builds():
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(ManualBuild.__table__.delete())
        await db.commit()
    yield


@pytest.mark.asyncio
async def test_manual_build_offer_poll_counters_and_persists(client, test_db):
    build_id = await _real_db_build(status="listed", ebay_listing_id="item-123", ebay_price=320.0)

    from app.workers.manual_build_lifecycle import run_manual_build_offer_poll_job

    with patch(
        "app.workers.manual_build_lifecycle._get_token", new=AsyncMock(return_value="TOKEN")
    ), patch(
        "app.workers.manual_build_lifecycle.ebay_trading_api.get_best_offers",
        new=AsyncMock(return_value=[{"best_offer_id": "off1", "price": 250.0, "status": "Active"}]),
    ), patch(
        "app.workers.manual_build_lifecycle.ebay_trading_api.respond_to_best_offer",
        new=AsyncMock(return_value=True),
    ):
        result = await run_manual_build_offer_poll_job()

    assert result["countered"] == 1

    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        refreshed = await db.get(ManualBuild, build_id)
        assert refreshed.counter_offer_round == 1
        assert refreshed.last_counter_offer_price == pytest.approx((250.0 + 320.0) / 2, abs=0.01)


@pytest.mark.asyncio
async def test_manual_build_recreate_cycle_steps_price_and_reschedules(client, test_db):
    build_id = await _real_db_build(
        status="listed",
        ebay_listing_id="item-123",
        ebay_listing_url="https://ebay.co.uk/itm/item-123",
        ebay_price=400.0,
        price_floor=352.0,
        sold_comp_target=310.0,
        generated_title="Old Title",
        generated_description="<p>old</p>",
        generated_aspects={"Brand": ["FlipFlop"], "Type": ["Desktop"]},
        photos=[{"url": "https://x/1.jpg", "kind": "photo"}, {"url": "https://x/2.jpg", "kind": "photo"}],
        listed_at=datetime.utcnow() - timedelta(days=8),
        next_recreate_at=datetime.utcnow() - timedelta(minutes=5),
    )

    from app.workers.manual_build_lifecycle import run_manual_build_recreate_cycle_job

    with patch(
        "app.services.ebay_browse.get_component_prices",
        new=AsyncMock(return_value={"used_prices": [300, 310], "new_prices": [], "used_median": 310}),
    ), patch(
        "app.workers.manual_build_lifecycle.post_build_to_ebay", new=AsyncMock(return_value="not_ready")
    ), patch(
        "app.api.manual_builds.ai_service.chat",
        new=AsyncMock(return_value=(
            '{"titles": ["New Title 1", "New Title 2"], "description": "<p>new</p>", '
            '"aspects": {"Brand": "FlipFlop", "Type": "Desktop"}}',
            "claude",
        )),
    ):
        result = await run_manual_build_recreate_cycle_job()

    assert result["recreated"] == 1

    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        refreshed = await db.get(ManualBuild, build_id)
        assert refreshed.recreate_cycle_count == 1
        assert refreshed.ebay_price < 400.0
        assert refreshed.next_recreate_at is not None
        assert refreshed.next_recreate_at > datetime.utcnow()
        assert refreshed.generated_title == "New Title 1"
        # Main photo swapped to the second one.
        assert refreshed.photos[0]["url"] == "https://x/2.jpg"


@pytest.mark.asyncio
async def test_manual_build_markdown_event_scan_flags_candidates(client, test_db):
    build_id = await _real_db_build(status="listed", markdown_event_opt_in=True, recreate_cycle_count=2)

    from app.workers.markdown_event import run_manual_build_markdown_event_scan_job

    with patch("app.workers.markdown_event.emit_alert", new=AsyncMock()):
        result = await run_manual_build_markdown_event_scan_job()

    assert result["flagged"] == 1


@pytest.mark.asyncio
async def test_post_to_ebay_promotes_when_opted_in(client, test_db):
    build_id = await _built_build(client, test_db)
    async with test_db() as db:
        build = await db.get(ManualBuild, build_id)
        build.generated_title = "Title"
        build.generated_description = "<p>desc</p>"
        build.generated_aspects = {"Brand": ["FlipFlop"], "Type": ["Desktop"]}
        build.photos = [{"url": "https://x/1.jpg", "kind": "photo"}]
        build.promoted_enabled = True
        build.promoted_ad_rate_pct = 6.0
        await db.commit()

    with patch(
        "app.services.ebay_token_manager.get_valid_ebay_access_token", new=AsyncMock(return_value="TOKEN")
    ), patch(
        "app.api.manual_builds.post_flip_to_ebay",
        new=AsyncMock(return_value={"success": True, "listing_id": "item-1", "url": "https://ebay.co.uk/itm/item-1", "sku": "sku-1"}),
    ), patch(
        "app.services.ebay_marketing.set_promoted_ad", new=AsyncMock(return_value=True)
    ) as mock_promote:
        resp = client.post(
            f"/api/manual-builds/{build_id}/post-to-ebay",
            json={"price": 320.0, "condition": "USED_EXCELLENT"},
        )

    assert resp.status_code == 200
    mock_promote.assert_awaited_once_with("item-1", 6.0, "TOKEN", "sandbox")


@pytest.mark.asyncio
async def test_post_to_ebay_starts_recreate_clock(client, test_db):
    build_id = await _built_build(client, test_db)
    async with test_db() as db:
        build = await db.get(ManualBuild, build_id)
        build.generated_title = "Title"
        build.generated_description = "<p>desc</p>"
        build.generated_aspects = {"Brand": ["FlipFlop"], "Type": ["Desktop"]}
        build.photos = [{"url": "https://x/1.jpg", "kind": "photo"}]
        await db.commit()

    with patch(
        "app.services.ebay_token_manager.get_valid_ebay_access_token", new=AsyncMock(return_value="TOKEN")
    ), patch(
        "app.api.manual_builds.post_flip_to_ebay",
        new=AsyncMock(return_value={"success": True, "listing_id": "item-1", "url": "https://ebay.co.uk/itm/item-1", "sku": "sku-1"}),
    ):
        resp = client.post(
            f"/api/manual-builds/{build_id}/post-to-ebay",
            json={"price": 320.0, "condition": "USED_EXCELLENT"},
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True

    async with test_db() as db:
        refreshed = await db.get(ManualBuild, build_id)
        assert refreshed.listed_at is not None
        assert refreshed.next_recreate_at is not None
