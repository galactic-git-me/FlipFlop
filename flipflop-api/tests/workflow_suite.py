import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import delete, select

from app.database import AsyncSessionLocal, engine, Base
from app.models.listing import Listing, ListingStatus, Classification
from app.models.flip import Flip
from app.models.flip_intelligence import FlipIntelligence
from app.models.source import DataSource, SourceType
from app.models.outcome_event import RetrainCheckpoint
from app.models.model_registry import ModelVersion, TrainingRun

from app.services import build_wizard as bw
from app.api.flips import create_flip, mark_sold, SoldPayload
from app.schemas.flip import FlipCreate
from app.services.demand_service import compute_demand, compute_auction_intel
from app.api.manual_submit import _run_pipeline
from app.services.retraining_pipeline import run_retraining_if_ready


@dataclass
class TestResult:
    name: str
    ok: bool
    detail: str = ""


async def _ensure_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(TrainingRun))
        await db.execute(delete(ModelVersion))
        await db.execute(delete(FlipIntelligence))
        await db.execute(delete(Flip))
        await db.execute(delete(Listing).where(Listing.external_id.like("wf-%")))
        await db.execute(delete(DataSource).where(DataSource.name.like("WF-%")))
        await db.execute(delete(RetrainCheckpoint).where(RetrainCheckpoint.name == "policy"))
        await db.commit()


async def test_build_wizard_owned_components() -> TestResult:
    name = "Build Wizard owned-components offset"
    original_composer = bw.composer_agent
    try:
        async def fake_composer(intent, playbook, attempt=1):
            return [
                bw.Build(
                    id="b1",
                    name="Owned GPU Build",
                    base_spec="OptiPlex i7 no gpu",
                    base_cost=120,
                    upgrades=[
                        bw.BuildUpgrade(role="gpu", item="RTX 3060", cost_estimate=170, source="eBay", required=True),
                        bw.BuildUpgrade(role="ssd", item="1TB SSD", cost_estimate=55, source="Amazon", required=False),
                    ],
                    total_cost=345,
                    estimated_resale=480,
                    estimated_profit=135,
                    profit_margin_pct=39.1,
                    risk="low",
                    demand_fit="good",
                    why="test",
                    sell_platform="eBay",
                    sell_price_target=479,
                )
            ]

        bw.composer_agent = fake_composer

        out = await bw.run_build_wizard(
            playbook={"name": "WF", "emoji": "🧪", "target_use_case": "gaming"},
            budget=500,
            user_notes="",
            priorities=["max profit"],
            constraints=[],
            owned_components=[{"name": "RTX 3060", "estimated_value": 170}],
        )

        b = out["builds"][0]
        assert b["owned_value_offset"] >= 170
        assert b["total_cost"] <= 175
        assert "owned-offset" in b["why"]
        return TestResult(name, True, f"total_cost={b['total_cost']}, offset={b['owned_value_offset']}")
    except Exception as e:
        return TestResult(name, False, str(e))
    finally:
        bw.composer_agent = original_composer


async def test_flip_workflow_recording() -> TestResult:
    name = "Flip workflow create->sold records intelligence"
    try:
        async with AsyncSessionLocal() as db:
            src = DataSource(name="WF-eBay", url="https://example.com", source_type=SourceType.scrape, enabled=True)
            db.add(src)
            await db.flush()

            listing = Listing(
                external_id="wf-listing-1",
                source_id=src.id,
                source_name=src.name,
                title="Dell OptiPlex 7070 i7",
                description="wf",
                price=220,
                url="https://example.com/wf-listing-1",
                image_urls=[],
                location="London",
                condition="used",
                cpu="Intel i7-9700",
                ram_gb=16,
                ram_type="DDR4",
                storage_gb=512,
                storage_type="SSD",
                gpu=None,
                has_psu=True,
                raw_specs={},
                gem_score=78,
                classification=Classification.gem,
                gem_signals=["undervalued"],
                estimated_resale=420,
                estimated_profit=120,
                estimated_upgrade_cost=30,
                initial_estimated_profit=120,
            )
            db.add(listing)
            await db.flush()

            flip = await create_flip(FlipCreate(listing_id=listing.id, notes="wf"), db)
            await mark_sold(flip.id, SoldPayload(actual_sale_price=450, sale_platform="ebay"), db)

            intel = (await db.execute(select(FlipIntelligence).where(FlipIntelligence.flip_id == flip.id))).scalar_one_or_none()
            assert intel is not None
            assert float(intel.profit) > 0
            return TestResult(name, True, f"profit={intel.profit:.2f}, roi={intel.roi_pct:.2f}")
    except Exception as e:
        return TestResult(name, False, str(e))


async def test_manual_pipeline() -> TestResult:
    name = "Manual submit pipeline saves scored listing"
    from app.api import manual_submit as ms

    original_resale = ms.get_resale_range
    original_score = ms.score_listing
    try:
        async def fake_resale(*args, **kwargs):
            return SimpleNamespace(median=380.0, low=340.0, high=430.0, count=12)

        def fake_score(**kwargs):
            return SimpleNamespace(classification=Classification.gem, score=82.0, signals=["manual_test"])

        ms.get_resale_range = fake_resale
        ms.score_listing = fake_score

        raw = SimpleNamespace(
            external_id="wf-manual-1",
            source_name="WF-Manual",
            title="Custom Ryzen build",
            description="Ryzen 7 + B650",
            price=260.0,
            url="https://example.com/manual",
            image_urls=[],
            location="Manchester",
            condition="used",
            listing_type="classified",
            listing_ends_at=None,
            seller_name="tester",
            seller_type="private",
        )

        async with AsyncSessionLocal() as db:
            listing = await _run_pipeline(raw, db)
            assert listing.external_id == "wf-manual-1"
            assert listing.classification == Classification.gem
            return TestResult(name, True, f"estimated_profit={float(listing.estimated_profit or 0):.2f}")
    except Exception as e:
        return TestResult(name, False, repr(e))
    finally:
        ms.get_resale_range = original_resale
        ms.score_listing = original_score


async def test_demand_workflow() -> TestResult:
    name = "Demand workflow categories + auction intel"
    try:
        async with AsyncSessionLocal() as db:
            src = DataSource(name="WF-Demand", url="https://example.com", source_type=SourceType.scrape, enabled=True)
            db.add(src)
            await db.flush()

            auction = Listing(
                external_id="wf-auction-1", source_id=src.id, source_name=src.name,
                title="Gaming PC RTX 3060 auction", description="wf", price=180, url="https://x/1", image_urls=[],
                location="Leeds", condition="used", cpu="i7", ram_gb=16, ram_type="DDR4", storage_gb=512,
                storage_type="SSD", gpu="RTX 3060", has_psu=True, raw_specs={},
                gem_score=80, classification=Classification.gem, gem_signals=["gpu"],
                estimated_resale=390, estimated_profit=130, estimated_upgrade_cost=20, initial_estimated_profit=130,
                status=ListingStatus.active, listing_type="auction", listing_ends_at=datetime.utcnow() + timedelta(hours=3),
            )
            db.add(auction)
            await db.flush()

            cats = await compute_demand(db)
            auctions = await compute_auction_intel(db, limit=10)
            assert len(cats) > 0
            assert any(c["name"] == "Gaming PCs" for c in cats)
            assert len(auctions) >= 1
            return TestResult(name, True, f"categories={len(cats)}, auctions={len(auctions)}")
    except Exception as e:
        return TestResult(name, False, str(e))


async def test_retraining_workflow() -> TestResult:
    name = "Retraining workflow creates model version"
    try:
        async with AsyncSessionLocal() as db:
            ck = RetrainCheckpoint(name="policy", last_flip_id=0, sold_flips_since=40, ready=True)
            db.add(ck)
            src = DataSource(name="WF-Retrain", url="https://example.com", source_type=SourceType.scrape, enabled=True)
            db.add(src)
            await db.flush()
            listing = Listing(
                external_id="wf-retrain-base",
                source_id=src.id,
                source_name=src.name,
                title="WF retrain listing",
                description="wf",
                price=200,
                url="https://example.com/wf-retrain",
                image_urls=[],
                location="UK",
                condition="used",
                cpu="i7",
                ram_gb=16,
                ram_type="DDR4",
                storage_gb=512,
                storage_type="SSD",
                gpu=None,
                has_psu=True,
                raw_specs={},
                gem_score=70,
                classification=Classification.gem,
                gem_signals=[],
                estimated_resale=360,
                estimated_profit=112,
                estimated_upgrade_cost=20,
                initial_estimated_profit=112,
            )
            db.add(listing)
            await db.flush()
            flips: list[Flip] = []
            for _ in range(40):
                f = Flip(listing_id=listing.id, base_cost=200.0, upgrade_cost=20.0, total_cost=220.0)
                db.add(f)
                flips.append(f)
            await db.flush()
            for i in range(40):
                db.add(
                    FlipIntelligence(
                        flip_id=flips[i].id,
                        source_site="WF",
                        buy_price=200.0,
                        gem_score_at_buy=70.0,
                        cpu_tier="i7",
                        had_gpu=False,
                        had_storage=True,
                        ram_gb=16,
                        case_theme=None,
                        upgrade_cost=20.0,
                        total_cost=220.0,
                        sell_price=360.0,
                        sell_platform="ebay",
                        days_to_sell=5,
                        profit=112.0,
                        roi_pct=50.9,
                    )
                )
            await db.commit()

        res = await run_retraining_if_ready(triggered_by="workflow_suite")
        assert res.get("ok") is True
        assert isinstance(res.get("version"), str)
        return TestResult(name, True, f"version={res.get('version')}")
    except Exception as e:
        return TestResult(name, False, repr(e))


async def main():
    await _ensure_schema()
    await _cleanup()

    tests = [
        test_build_wizard_owned_components,
        test_flip_workflow_recording,
        test_manual_pipeline,
        test_demand_workflow,
        test_retraining_workflow,
    ]

    results = []
    for t in tests:
        results.append(await t())

    print("\\nWorkflow Test Suite Results")
    print("=" * 80)
    passed = 0
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"[{status}] {r.name}")
        if r.detail:
            print(f"       {r.detail}")
        if r.ok:
            passed += 1
    print("-" * 80)
    print(f"Passed {passed}/{len(results)}")

    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
