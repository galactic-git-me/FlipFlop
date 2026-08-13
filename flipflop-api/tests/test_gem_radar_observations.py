"""Tests for price-history recording, change/relisting detection, and the
cross-scan research cache (PRD §23-24, §31).
"""
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.gem_radar_observation import GemRadarListingObservation
from app.gem_radar.observations import (
    cleanup_old_observations,
    compute_watch_signals,
    detect_relisting,
    get_cached_research,
    get_previous_observation,
    record_observation,
    store_cached_research,
)
from app.gem_radar.schemas import BenchmarkStat, ExtractedListing, Identity, PriceBundle


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(GemRadarListingObservation.metadata.create_all, tables=[GemRadarListingObservation.__table__])
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


def _listing(
    listing_id="1", price=50.0, postage=0.0, bid_count=None, best_offer=False, condition="used",
    seller="teesside_tek", title="Ryzen 7 5700X", extracted_at=None,
) -> ExtractedListing:
    return ExtractedListing(
        listingId=listing_id, url=f"https://www.ebay.co.uk/itm/{listing_id}", title=title, seller=seller,
        sellerFeedbackPercent=99.0, sellerFeedbackCount=100, conditionRaw=condition, conditionNormalised=condition,
        itemPrice=price, postagePrice=postage, currentDeliveredPrice=price + postage, listingType="buy_it_now",
        bestOfferEnabled=best_offer, bidCount=bid_count, auctionEndAt=None, imageUrl=None, sponsored=False,
        extractedAt=extracted_at or datetime.now(timezone.utc),
    )


def _unavailable() -> BenchmarkStat:
    return BenchmarkStat(
        status="unavailable", average=None, median=None, trimmedMean=None, min=None, max=None,
        sampleSize=0, validSampleSize=0, matchLevelCounts={}, exclusions=[], source="x", sourceUrl=None,
        observedAt=None, ageMinutes=None, unavailableReason="no data",
    )


class TestObservationRecording:
    @pytest.mark.asyncio
    async def test_first_sighting_has_no_previous_observation(self, db):
        listing = _listing()
        previous = await get_previous_observation(db, listing.listing_id)
        assert previous is None
        await record_observation(db, listing, category="cpu")
        # A second call for a DIFFERENT listing still sees no history.
        assert await get_previous_observation(db, "different-id") is None

    @pytest.mark.asyncio
    async def test_second_sighting_finds_the_first_as_previous(self, db):
        listing = _listing(price=50)
        await record_observation(db, listing, category="cpu")
        previous = await get_previous_observation(db, listing.listing_id)
        assert previous is not None
        assert previous.delivered_price == 50


class TestWatchSignals:
    @pytest.mark.asyncio
    async def test_first_sighting_has_no_price_drop_and_one_observation(self, db):
        listing = _listing()
        signals = await compute_watch_signals(db, listing, previous=None)
        assert signals.price_drop_detected is False
        assert signals.observation_count == 1

    @pytest.mark.asyncio
    async def test_price_drop_detected_against_previous(self, db):
        first = _listing(price=100)
        await record_observation(db, first, category="cpu")
        previous = await get_previous_observation(db, first.listing_id)

        second = _listing(price=80)
        signals = await compute_watch_signals(db, second, previous)
        assert signals.price_drop_detected is True
        assert signals.price_drop_amount == 20
        assert signals.price_drop_percent == 20.0

    @pytest.mark.asyncio
    async def test_price_increase_is_not_a_price_drop(self, db):
        first = _listing(price=80)
        await record_observation(db, first, category="cpu")
        previous = await get_previous_observation(db, first.listing_id)

        second = _listing(price=100)
        signals = await compute_watch_signals(db, second, previous)
        assert signals.price_drop_detected is False
        assert signals.price_drop_amount is None

    @pytest.mark.asyncio
    async def test_bid_count_and_best_offer_changes_detected(self, db):
        first = _listing(bid_count=2, best_offer=False)
        await record_observation(db, first, category="cpu")
        previous = await get_previous_observation(db, first.listing_id)

        second = _listing(bid_count=5, best_offer=True)
        signals = await compute_watch_signals(db, second, previous)
        assert signals.bid_count_changed is True
        assert signals.best_offer_newly_enabled is True

    @pytest.mark.asyncio
    async def test_condition_change_detected(self, db):
        first = _listing(condition="used")
        await record_observation(db, first, category="cpu")
        previous = await get_previous_observation(db, first.listing_id)

        second = _listing(condition="parts_only")
        signals = await compute_watch_signals(db, second, previous)
        assert signals.condition_changed is True


class TestRelistingDetection:
    @pytest.mark.asyncio
    async def test_no_relisting_without_a_seller_name(self, db):
        listing = _listing(listing_id="222", seller=None)
        assert await detect_relisting(db, listing) is None

    @pytest.mark.asyncio
    async def test_no_relisting_when_no_prior_listings_exist(self, db):
        listing = _listing(listing_id="333")
        assert await detect_relisting(db, listing) is None

    @pytest.mark.asyncio
    async def test_detects_relisting_after_quiet_period(self, db):
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        old_listing = _listing(listing_id="old-1", title="Ryzen 7 5700X 8-core CPU", extracted_at=old_time)
        await record_observation(db, old_listing, category="cpu")

        new_listing = _listing(listing_id="new-1", title="Ryzen 7 5700X 8 Core Processor")
        result = await detect_relisting(db, new_listing)
        assert result == "old-1"

    @pytest.mark.asyncio
    async def test_no_relisting_for_dissimilar_title(self, db):
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        old_listing = _listing(listing_id="old-2", title="Ryzen 7 5700X CPU", extracted_at=old_time)
        await record_observation(db, old_listing, category="cpu")

        new_listing = _listing(listing_id="new-2", title="Corsair 16GB DDR4 RAM Kit")
        assert await detect_relisting(db, new_listing) is None

    @pytest.mark.asyncio
    async def test_no_relisting_for_still_active_listing(self, db):
        # Same seller/title but observed recently — still active, not a relisting.
        recent_listing = _listing(listing_id="active-1", title="Ryzen 7 5700X CPU")
        await record_observation(db, recent_listing, category="cpu")

        new_listing = _listing(listing_id="active-2", title="Ryzen 7 5700X CPU")
        assert await detect_relisting(db, new_listing) is None


class TestResearchCache:
    @pytest.mark.asyncio
    async def test_no_cache_before_anything_is_stored(self, db):
        assert await get_cached_research(db, "1", max_age_minutes=120) is None

    @pytest.mark.asyncio
    async def test_cache_round_trips(self, db):
        listing = _listing()
        await record_observation(db, listing, category="cpu")
        identity = Identity(brand="AMD", model="Ryzen 7 5700X", mpn=None, category="cpu", exactSkuConfidence=0.8)
        prices = PriceBundle(
            actualListing=50, ebayNewBin=_unavailable(), ebayUsedBin=_unavailable(),
            ebayNewSold=_unavailable(), ebayUsedSold=_unavailable(), amazonUkNew=_unavailable(),
        )
        await store_cached_research(db, listing.listing_id, identity, prices, "test reasoning")

        cached = await get_cached_research(db, listing.listing_id, max_age_minutes=120)
        assert cached is not None
        assert cached.identity.model == "Ryzen 7 5700X"
        assert cached.reasoning_summary == "test reasoning"

    @pytest.mark.asyncio
    async def test_cache_expires_past_max_age(self, db):
        listing = _listing()
        await record_observation(db, listing, category="cpu")
        identity = Identity(brand="AMD", model="Ryzen 7 5700X", mpn=None, category="cpu", exactSkuConfidence=0.8)
        prices = PriceBundle(
            actualListing=50, ebayNewBin=_unavailable(), ebayUsedBin=_unavailable(),
            ebayNewSold=_unavailable(), ebayUsedSold=_unavailable(), amazonUkNew=_unavailable(),
        )
        await store_cached_research(db, listing.listing_id, identity, prices, None)

        assert await get_cached_research(db, listing.listing_id, max_age_minutes=0) is None


class TestRetentionCleanup:
    @pytest.mark.asyncio
    async def test_deletes_old_observations_not_preserved(self, db):
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        listing = _listing(listing_id="stale-1", extracted_at=old_time)
        await record_observation(db, listing, category="cpu")

        removed = await cleanup_old_observations(db, retention_days=90, preserve_listing_ids=set())
        assert removed == 1

    @pytest.mark.asyncio
    async def test_preserves_purchased_listing_observations(self, db):
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        listing = _listing(listing_id="purchased-1", extracted_at=old_time)
        await record_observation(db, listing, category="cpu")

        removed = await cleanup_old_observations(db, retention_days=90, preserve_listing_ids={"purchased-1"})
        assert removed == 0

    @pytest.mark.asyncio
    async def test_keeps_recent_observations(self, db):
        listing = _listing(listing_id="fresh-1")
        await record_observation(db, listing, category="cpu")
        removed = await cleanup_old_observations(db, retention_days=90, preserve_listing_ids=set())
        assert removed == 0
