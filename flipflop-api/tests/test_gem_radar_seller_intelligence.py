"""Tests for seller-profile aggregation (PRD §25)."""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.gem_radar_seller_profile import GemRadarSellerProfile
from app.gem_radar.schemas import ExtractedListing
from app.gem_radar.seller_intelligence import get_seller_profile, increment_purchase_count, upsert_seller_profile


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(GemRadarSellerProfile.metadata.create_all, tables=[GemRadarSellerProfile.__table__])
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


def _listing(seller="teesside_tek", feedback_pct=99.0, feedback_count=100) -> ExtractedListing:
    return ExtractedListing(
        listingId="1", url="https://www.ebay.co.uk/itm/1", title="Ryzen 7 5700X", seller=seller,
        sellerFeedbackPercent=feedback_pct, sellerFeedbackCount=feedback_count, conditionRaw="used",
        conditionNormalised="used", itemPrice=50, postagePrice=0, currentDeliveredPrice=50,
        listingType="buy_it_now", bestOfferEnabled=False, bidCount=None, auctionEndAt=None, imageUrl=None,
        sponsored=False, extractedAt=datetime.now(timezone.utc),
    )


class TestUpsertSellerProfile:
    @pytest.mark.asyncio
    async def test_no_profile_created_without_a_seller_name(self, db):
        listing = _listing(seller=None)
        profile = await upsert_seller_profile(db, listing, "OK_DEAL")
        assert profile is None

    @pytest.mark.asyncio
    async def test_creates_profile_on_first_sighting(self, db):
        profile = await upsert_seller_profile(db, _listing(), "OK_DEAL")
        assert profile.seller_name == "teesside_tek"
        assert profile.observed_listings_count == 1
        assert profile.historical_gem_count == 0

    @pytest.mark.asyncio
    async def test_gem_and_super_gem_increment_historical_gem_count(self, db):
        await upsert_seller_profile(db, _listing(), "GEM")
        profile = await upsert_seller_profile(db, _listing(), "SUPER_GEM")
        assert profile.observed_listings_count == 2
        assert profile.historical_gem_count == 2  # both GEM and SUPER_GEM count as gems
        assert profile.historical_super_gem_count == 1

    @pytest.mark.asyncio
    async def test_average_and_poor_deals_do_not_increment_gem_count(self, db):
        await upsert_seller_profile(db, _listing(), "AVERAGE_DEAL")
        profile = await upsert_seller_profile(db, _listing(), "POOR_DEAL")
        assert profile.observed_listings_count == 2
        assert profile.historical_gem_count == 0

    @pytest.mark.asyncio
    async def test_missing_feedback_does_not_overwrite_known_value(self, db):
        await upsert_seller_profile(db, _listing(feedback_pct=98.5, feedback_count=500), "OK_DEAL")
        profile = await upsert_seller_profile(db, _listing(feedback_pct=None, feedback_count=None), "OK_DEAL")
        assert profile.feedback_percent == 98.5
        assert profile.feedback_count == 500


class TestIncrementPurchaseCount:
    @pytest.mark.asyncio
    async def test_increments_existing_profile(self, db):
        await upsert_seller_profile(db, _listing(), "GEM")
        await increment_purchase_count(db, "teesside_tek")
        profile = await get_seller_profile(db, "teesside_tek")
        assert profile.historical_purchase_count == 1

    @pytest.mark.asyncio
    async def test_no_op_for_unknown_seller(self, db):
        # Must not raise — a Bought It for a seller Gem Radar has never
        # scanned (e.g. manually entered listing) is a valid, if rare, case.
        await increment_purchase_count(db, "never-seen-before")


class TestGetSellerProfile:
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_seller(self, db):
        assert await get_seller_profile(db, "nobody") is None

    @pytest.mark.asyncio
    async def test_returns_populated_profile(self, db):
        await upsert_seller_profile(db, _listing(), "SUPER_GEM")
        profile = await get_seller_profile(db, "teesside_tek")
        assert profile.seller_name == "teesside_tek"
        assert profile.historical_super_gem_count == 1
