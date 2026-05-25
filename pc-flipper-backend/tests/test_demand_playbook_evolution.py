from __future__ import annotations

from datetime import datetime, timedelta
import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal, Base, engine
from app.models.external_demand_signal import ExternalDemandSignal
from app.models.flip import Flip, FlipStage
from app.models.listing import Classification, Listing, ListingStatus
from app.models.playbook import Playbook, PlaybookProposal
from app.services import external_demand as ext
from app.services import playbook_evolution as pe

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _ensure_schema() -> None:
    # Avoid reusing asyncpg connections bound to a prior event loop.
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _cleanup() -> None:
    # Ensure pooled connections don't leak across test loop boundaries.
    await engine.dispose()
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PlaybookProposal))
        await db.execute(delete(Playbook).where(Playbook.name.like("TEST-%")))
        await db.execute(delete(Flip).where(Flip.notes == "TEST-demand"))
        await db.execute(delete(Listing).where(Listing.external_id.like("test-demand-%")))
        await db.execute(delete(ExternalDemandSignal).where(ExternalDemandSignal.topic.like("test-%")))
        await db.commit()


async def test_external_demand_ingest_and_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    await _ensure_schema()
    await _cleanup()

    now = datetime.utcnow()

    async def fake_reddit(topic, queries, signal_now):
        return [
            ext.DemandSignal(
                source="reddit",
                topic=f"test-{topic}",
                query="q1",
                score=42.0,
                confidence=0.6,
                sample_size=12,
                signal_time=signal_now,
                notes="test",
            )
        ]

    async def fake_trends(topic, queries, signal_now):
        return [
            ext.DemandSignal(
                source="google_trends",
                topic=f"test-{topic}",
                query="q2",
                score=55.0,
                confidence=0.7,
                sample_size=20,
                signal_time=signal_now,
                notes="test",
            )
        ]

    async def fake_steam(topic, queries, signal_now):
        return [
            ext.DemandSignal(
                source="steam_hardware",
                topic=f"test-{topic}",
                query="q3",
                score=25.0,
                confidence=0.5,
                sample_size=8,
                signal_time=signal_now,
                notes="test",
            )
        ]

    monkeypatch.setattr(ext, "_fetch_reddit_signals", fake_reddit)
    monkeypatch.setattr(ext, "_fetch_google_trends_signals", fake_trends)
    monkeypatch.setattr(ext, "_fetch_steam_signals", fake_steam)

    result = await ext.ingest_external_demand_signals()
    assert result["ok"] is True
    assert result["topics"] == len(ext.TOPIC_QUERIES)
    assert result["inserted"] == len(ext.TOPIC_QUERIES) * 3

    snapshot = await ext.latest_external_signal_snapshot(limit_per_source=50)
    assert "reddit" in snapshot["summary"]
    assert "google_trends" in snapshot["summary"]
    assert "steam_hardware" in snapshot["summary"]
    assert snapshot["summary"]["reddit"]["count"] >= len(ext.TOPIC_QUERIES)
    assert snapshot["summary"]["google_trends"]["avg_score"] > 0
    assert snapshot["summary"]["steam_hardware"]["avg_confidence"] > 0


async def test_playbook_evolution_creates_demand_driven_playbook_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    await _ensure_schema()
    await _cleanup()

    async with AsyncSessionLocal() as db:
        db.add(
            Playbook(
                name="TEST-Office",
                status="active",
                target_use_case="office",
                profit_strategy={"target_profit_gbp": 80},
            )
        )
        await db.commit()

    async def fake_compute_demand(_db):
        return [
            {
                "name": "HTPC / SFF",
                "count": 120,
                "gem_count": 22,
                "trend": "rising",
                "strength": "High",
            }
        ]

    async def fake_external_snapshot(limit_per_source=15):
        return {"summary": {"reddit": {"count": 5, "avg_score": 40.0, "avg_confidence": 0.6}}, "items": {}}

    monkeypatch.setattr(pe, "compute_demand", fake_compute_demand)
    monkeypatch.setattr(pe, "latest_external_signal_snapshot", fake_external_snapshot)

    async with AsyncSessionLocal() as db:
        active_use_cases = {
            str(pb.target_use_case or "").lower()
            for pb in (await db.execute(select(Playbook).where(Playbook.status == "active"))).scalars().all()
        }

    result = await pe.run_playbook_evolution()
    assert result["ok"] is True

    async with AsyncSessionLocal() as db:
        proposals = (
            await db.execute(
                select(PlaybookProposal).where(
                    PlaybookProposal.action == "CREATE",
                    PlaybookProposal.status == "pending",
                )
            )
        ).scalars().all()
        if "htpc" in active_use_cases:
            assert not proposals
            assert result["proposals_created"] >= 0
        else:
            assert proposals, "Expected at least one pending CREATE proposal"
            p = proposals[0]
            assert (p.proposed_data or {}).get("target_use_case") == "htpc"
            assert (p.demand_signals or {}).get("category") == "HTPC / SFF"
            assert result["proposals_created"] >= 1


async def test_playbook_evolution_creates_update_proposal_from_sold_performance(monkeypatch: pytest.MonkeyPatch) -> None:
    await _ensure_schema()
    await _cleanup()

    playbook_id: int | None = None

    async with AsyncSessionLocal() as db:
        pb = Playbook(
            name="TEST-Gaming",
            status="active",
            target_use_case="gaming",
            profit_strategy={"target_profit_gbp": 100},
        )
        db.add(pb)
        await db.flush()
        playbook_id = pb.id

        listing = Listing(
            external_id="test-demand-listing-1",
            source_id=1,
            source_name="TEST",
            source_confidence="browser_verified",
            title="TEST listing",
            description="test",
            price=200.0,
            url="https://example.com/test-demand-listing-1",
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
            gem_score=70.0,
            classification=Classification.gem,
            gem_signals=["test"],
            estimated_resale=380.0,
            estimated_profit=120.0,
            estimated_upgrade_cost=20.0,
            initial_estimated_profit=120.0,
            status=ListingStatus.active,
        )
        db.add(listing)
        await db.flush()

        db.add(
            Flip(
                listing_id=listing.id,
                stage=FlipStage.sold,
                notes="TEST-demand",
                sold_at=datetime.utcnow() - timedelta(days=2),
                actual_profit=180.0,
                base_cost=200.0,
                upgrade_cost=20.0,
                total_cost=220.0,
                actual_sale_price=450.0,
                sale_platform="ebay",
            )
        )
        await db.commit()

    async def fake_compute_demand(_db):
        return []

    async def fake_external_snapshot(limit_per_source=15):
        return {"summary": {}, "items": {}}

    monkeypatch.setattr(pe, "compute_demand", fake_compute_demand)
    monkeypatch.setattr(pe, "latest_external_signal_snapshot", fake_external_snapshot)

    result = await pe.run_playbook_evolution()
    assert result["ok"] is True
    assert result["sold_flips"] >= 1

    async with AsyncSessionLocal() as db:
        update_props = (
            await db.execute(
                select(PlaybookProposal).where(
                    PlaybookProposal.action == "UPDATE",
                    PlaybookProposal.playbook_id == playbook_id,
                    PlaybookProposal.status == "pending",
                )
            )
        ).scalars().all()
        assert update_props, "Expected pending UPDATE proposal"
        updated = update_props[0]
        new_target = float((updated.proposed_data or {}).get("profit_strategy", {}).get("target_profit_gbp", 0))
        assert new_target > 100.0
        assert float((updated.demand_signals or {}).get("avg_actual_profit", 0)) > 0.0
