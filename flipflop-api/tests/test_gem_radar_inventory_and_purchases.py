"""DB-backed tests for inventory awareness and the Bought It workflow.

Uses a self-contained in-memory SQLite engine (only creating the two tables
under test) rather than relying on a shared conftest fixture, since no such
fixture exists in this repo yet for async tests.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.models.gem_radar_seller_profile import GemRadarSellerProfile
from app.gem_radar.inventory_match import fetch_inventory_awareness
from app.gem_radar.purchases import create_provisional_purchase
from app.gem_radar.schemas import BoughtItPayload


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            InventoryItem.metadata.create_all,
            tables=[InventoryItem.__table__, InventoryAllocation.__table__, GemRadarSellerProfile.__table__],
        )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


def _bought_it_payload(listing_id: str = "111", price: float = 55.0) -> BoughtItPayload:
    return BoughtItPayload(
        source="gem_radar_extension",
        marketplace="ebay_uk",
        listingId=listing_id,
        listingUrl=f"https://www.ebay.co.uk/itm/{listing_id}",
        title="Ryzen 7 5700X",
        seller="teesside_tek",
        actualItemPricePaid=price,
        postagePaid=2.70,
        discountAmount=0,
        totalPaid=price + 2.70,
        quantity=1,
        purchaseDate=datetime.now(timezone.utc),
        notes="",
    )


class TestBoughtIt:
    @pytest.mark.asyncio
    async def test_creates_provisional_purchase(self, db):
        response = await create_provisional_purchase(db, _bought_it_payload())
        assert response.duplicate_of is None
        assert response.status == "PURCHASED_MANUAL"
        assert response.reconciliation_status == "PENDING_EMAIL_CONFIRMATION"

    @pytest.mark.asyncio
    async def test_duplicate_bought_it_does_not_create_a_second_row(self, db):
        first = await create_provisional_purchase(db, _bought_it_payload(listing_id="222"))
        second = await create_provisional_purchase(db, _bought_it_payload(listing_id="222"))
        assert second.duplicate_of == first.inventory_item_id

    @pytest.mark.asyncio
    async def test_different_listings_create_different_rows(self, db):
        first = await create_provisional_purchase(db, _bought_it_payload(listing_id="333"))
        second = await create_provisional_purchase(db, _bought_it_payload(listing_id="444"))
        assert first.inventory_item_id != second.inventory_item_id
        assert second.duplicate_of is None


class TestInventoryAwareness:
    @pytest.mark.asyncio
    async def test_counts_reflect_owned_quantity_not_score(self, db):
        db.add(InventoryItem(component_name="Ryzen 7 5700X", component_type="cpu", quantity=3, base_price=80))
        db.add(InventoryItem(component_name="Ryzen 5 5600", component_type="cpu", quantity=2, base_price=60))
        await db.commit()

        awareness = await fetch_inventory_awareness(db, category="cpu", model="5700X", brand=None)
        assert awareness.same_model_owned == 3
        assert awareness.category_count == 5  # both CPUs counted for category total
        assert awareness.available_count == 5  # nothing reserved yet

    @pytest.mark.asyncio
    async def test_reserved_quantity_reduces_available_not_category_count(self, db):
        item = InventoryItem(component_name="Ryzen 7 5700X", component_type="cpu", quantity=3, base_price=80)
        db.add(item)
        await db.commit()
        await db.refresh(item)

        db.add(InventoryAllocation(inventory_item_id=item.id, flip_id=1, quantity_allocated=1, cost_per_unit_at_allocation=80))
        await db.commit()

        awareness = await fetch_inventory_awareness(db, category="cpu", model=None, brand=None)
        assert awareness.category_count == 3
        assert awareness.reserved_count == 1
        assert awareness.available_count == 2

    @pytest.mark.asyncio
    async def test_no_matches_returns_zeros_not_an_error(self, db):
        awareness = await fetch_inventory_awareness(db, category="gpu", model="RTX 4090", brand=None)
        assert awareness.exact_matches_owned == 0
        assert awareness.same_model_owned == 0
        assert awareness.category_count == 0
