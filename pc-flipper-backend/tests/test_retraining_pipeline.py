import asyncio
from datetime import datetime

from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models.flip_intelligence import FlipIntelligence
from app.models.model_registry import ModelVersion, TrainingRun
from app.models.outcome_event import RetrainCheckpoint
from app.services.retraining_pipeline import run_retraining_if_ready, promote_model_version, rollback_to_previous_active


async def _seed_samples(n: int) -> None:
    async with AsyncSessionLocal() as db:
        for i in range(n):
            db.add(
                FlipIntelligence(
                    flip_id=10_000 + i,
                    buy_price=300,
                    sell_price=450,
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
    async with AsyncSessionLocal() as db:
        await db.execute(delete(TrainingRun))
        await db.execute(delete(ModelVersion))
        await db.execute(delete(FlipIntelligence).where(FlipIntelligence.flip_id >= 10000))
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

    rolled = await rollback_to_previous_active()
    # rollback may fail if only one version exists; create one more and retry
    if not rolled.get("ok"):
        async with AsyncSessionLocal() as db:
            db.add(
                ModelVersion(
                    model_name="policy",
                    version="v-test-older",
                    status="trained",
                    score_profit_mae=10.0,
                    score_roi_mae=4.0,
                    trained_on_samples=40,
                    artifact_path="/tmp/test",
                )
            )
            await db.commit()
        rolled = await rollback_to_previous_active()
    assert rolled.get("ok") is True, rolled


if __name__ == "__main__":
    asyncio.run(main())
    print("test_retraining_pipeline: ok")
