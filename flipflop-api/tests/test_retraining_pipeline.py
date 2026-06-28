import asyncio
from datetime import datetime

from sqlalchemy import delete

from app.database import AsyncSessionLocal, engine, Base
from app.models.flip import Flip
from app.models.flip_intelligence import FlipIntelligence
from app.models.listing import Listing
from app.models.model_registry import ModelVersion, TrainingRun
from app.models.outcome_event import RetrainCheckpoint
from app.services.retraining_pipeline import run_retraining_if_ready, promote_model_version, rollback_to_previous_active


async def _seed_samples(n: int) -> None:
    async with AsyncSessionLocal() as db:
        listing = Listing(
            external_id="test-listing-rt",
            source_id=1,
            source_name="eBay",
            title="Test Desktop PC",
            description="test",
            price=300.0,
            url="https://example.com/test-listing",
            image_urls=[],
            location="London",
            condition="used",
            cpu="Intel i7",
            ram_gb=16,
            ram_type="DDR4",
            storage_gb=512,
            storage_type="SSD",
            gpu=None,
            has_psu=True,
            raw_specs={},
            gem_score=75.0,
            gem_signals=[],
            estimated_resale=450.0,
            estimated_profit=120.0,
            estimated_upgrade_cost=20.0,
            initial_estimated_profit=120.0,
        )
        db.add(listing)
        await db.flush()

        flips: list[Flip] = []
        for _ in range(n):
            f = Flip(listing_id=listing.id, base_cost=300.0, upgrade_cost=20.0, total_cost=320.0)
            db.add(f)
            flips.append(f)
        await db.flush()

        for i in range(n):
            db.add(
                FlipIntelligence(
                    flip_id=flips[i].id,
                    buy_price=300,
                    sell_price=450,
                    total_cost=320,
                    upgrade_cost=20,
                    had_gpu=False,
                    had_storage=True,
                    profit=150 + (i % 5),
                    roi_pct=40 + (i % 3),
                    days_to_sell=6 + (i % 4),
                    source_site="eBay",
                    cpu_tier="i7",
                    sell_platform="ebay",
                    case_theme=None,
                    gem_score_at_buy=74,
                    created_at=datetime.utcnow(),
                )
            )
        await db.commit()


async def _reset() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(TrainingRun))
        await db.execute(delete(ModelVersion))
        await db.execute(delete(FlipIntelligence))
        await db.execute(delete(Flip))
        await db.execute(delete(Listing).where(Listing.external_id == "test-listing-rt"))
        await db.execute(delete(RetrainCheckpoint).where(RetrainCheckpoint.name == "policy"))
        db.add(RetrainCheckpoint(name="policy", last_flip_id=0, sold_flips_since=0, ready=True))
        await db.commit()


async def main() -> None:
    await _reset()
    await _seed_samples(40)

    trained = await run_retraining_if_ready(triggered_by="test")
    assert trained.get("ok") is True, trained
    version = trained.get("version")
    assert isinstance(version, str) and version

    promoted = await promote_model_version(version)
    assert promoted.get("ok") is True, promoted

    async with AsyncSessionLocal() as db:
        db.add(
            ModelVersion(
                model_name="policy",
                version="v-test-newer",
                status="trained",
                score_profit_mae=9.0,
                score_roi_mae=3.8,
                trained_on_samples=40,
                artifact_path="/tmp/test-newer",
            )
        )
        await db.commit()
    promoted_newer = await promote_model_version("v-test-newer")
    assert promoted_newer.get("ok") is True, promoted_newer

    rolled = await rollback_to_previous_active()
    assert rolled.get("ok") is True, rolled


if __name__ == "__main__":
    asyncio.run(main())
    print("test_retraining_pipeline: ok")
