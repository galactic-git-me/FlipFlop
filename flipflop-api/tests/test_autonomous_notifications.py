from __future__ import annotations

from datetime import datetime
import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal, Base, engine
from app.models.alert_event import AlertEvent
from app.models.listing import Listing, Classification, ListingStatus
from app.models.flip import Flip
from app.models.flip_intelligence import FlipIntelligence
from app.models.source import DataSource, SourceType
from app.models.playbook import Playbook, PlaybookProposal
from app.models.search_telemetry import SearchTelemetry
from app.models.source_search_term import SourceSearchTerm
from app.api.flips import mark_sold, SoldPayload
from app.api.playbooks import approve_proposal
from app.schemas.playbook import ProposalResolve
from app.services import search_telemetry as st
from app.services import autonomous_loop as al

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _cleanup() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AlertEvent))
        await db.execute(delete(SearchTelemetry))
        await db.execute(delete(SourceSearchTerm).where(SourceSearchTerm.term.like("TEST-%")))
        await db.execute(delete(PlaybookProposal))
        await db.execute(delete(Playbook).where(Playbook.name.like("TEST-%")))
        await db.execute(delete(FlipIntelligence))
        await db.execute(delete(Flip))
        await db.execute(delete(Listing).where(Listing.external_id.like("test-auto-%")))
        await db.execute(delete(DataSource).where(DataSource.name.like("TEST-%")))
        await db.commit()


async def test_zero_result_term_auto_deleted_and_alerted() -> None:
    await _ensure_schema()
    await _cleanup()

    async with AsyncSessionLocal() as db:
        db.add(
            SourceSearchTerm(
                scope="accessories",
                group_name="TEST",
                term="TEST-zero-term",
                source_names=["eBay", "Amazon"],
                enabled=True,
            )
        )
        db.add_all(
            [
                SearchTelemetry(
                    ts=datetime.utcnow(),
                    source="Accessories:eBay",
                    term="TEST-zero-term",
                    found=0,
                    new=0,
                    error=None,
                ),
                SearchTelemetry(
                    ts=datetime.utcnow(),
                    source="Accessories:Amazon",
                    term="TEST-zero-term",
                    found=0,
                    new=0,
                    error=None,
                ),
            ]
        )
        await db.commit()

    await st._cleanup_zero_terms(window_days=3)

    async with AsyncSessionLocal() as db:
        term = (
            await db.execute(
                select(SourceSearchTerm).where(SourceSearchTerm.term == "TEST-zero-term")
            )
        ).scalar_one_or_none()
        assert term is None

        alerts = (
            await db.execute(
                select(AlertEvent).where(AlertEvent.code == "auto_deleted_zero_search_term")
            )
        ).scalars().all()
        assert alerts
        assert "TEST-zero-term" in (alerts[0].message or "")


async def test_demand_driven_playbook_apply_emits_alert() -> None:
    await _ensure_schema()
    await _cleanup()

    async with AsyncSessionLocal() as db:
        pb = Playbook(
            name="TEST-Playbook",
            status="active",
            target_use_case="gaming",
            profit_strategy={"target_profit_gbp": 100},
        )
        db.add(pb)
        await db.flush()

        proposal = PlaybookProposal(
            action="UPDATE",
            playbook_id=pb.id,
            proposed_data={"profit_strategy": {"target_profit_gbp": 110}},
            reason="test-demand-apply",
            demand_signals={"source": "demand_engine_v1"},
            status="pending",
            proposed_at=datetime.utcnow(),
        )
        db.add(proposal)
        await db.commit()
        proposal_id = proposal.id

    async with AsyncSessionLocal() as db:
        await approve_proposal(
            proposal_id=proposal_id,
            body=ProposalResolve(approved=True, resolved_by="test"),
            db=db,
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        alerts = (
            await db.execute(
                select(AlertEvent).where(AlertEvent.code == "playbook_demand_change_applied")
            )
        ).scalars().all()
        assert alerts
        assert "TEST-Playbook" in (alerts[0].message or "")


async def test_resale_detection_emits_profit_alert() -> None:
    await _ensure_schema()
    await _cleanup()

    async with AsyncSessionLocal() as db:
        src = DataSource(
            name="TEST-Source",
            url="https://example.com",
            source_type=SourceType.scrape,
            enabled=True,
        )
        db.add(src)
        await db.flush()

        listing = Listing(
            external_id="test-auto-listing-1",
            source_id=src.id,
            source_name=src.name,
            source_confidence="browser_verified",
            title="TEST resale listing",
            description="test",
            price=200.0,
            url="https://example.com/test-auto-listing-1",
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
            gem_score=75.0,
            classification=Classification.gem,
            gem_signals=["test"],
            estimated_resale=350.0,
            estimated_profit=100.0,
            estimated_upgrade_cost=20.0,
            initial_estimated_profit=100.0,
            status=ListingStatus.active,
        )
        db.add(listing)
        await db.flush()

        flip = Flip(
            listing_id=listing.id,
            base_cost=200.0,
            upgrade_cost=20.0,
            total_cost=220.0,
        )
        db.add(flip)
        await db.commit()
        flip_id = flip.id

    async with AsyncSessionLocal() as db:
        await mark_sold(
            flip_id=flip_id,
            body=SoldPayload(actual_sale_price=420.0, sale_platform="ebay"),
            db=db,
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        alert = (
            await db.execute(
                select(AlertEvent).where(AlertEvent.code == "flip_resale_detected")
            )
        ).scalars().first()
        assert alert is not None
        assert "profit £" in (alert.message or "")


async def test_autonomous_cycle_orchestrates_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sourcing():
        return {"ok": True, "lane": "sourcing"}

    async def fake_demand():
        return {"ok": True, "lane": "demand"}

    async def fake_evolution():
        return {"ok": True, "lane": "evolution"}

    async def fake_outcomes():
        return {"ok": True, "lane": "outcomes"}

    monkeypatch.setattr(al, "run_flip_opportunities_swarm", fake_sourcing)
    monkeypatch.setattr(al, "ingest_external_demand_signals", fake_demand)
    monkeypatch.setattr(al, "run_playbook_evolution", fake_evolution)
    monkeypatch.setattr(al, "capture_outcomes_and_check_retrain", fake_outcomes)

    result = await al.run_autonomous_cycle()
    assert result["ok"] is True
    assert result["steps"]["sourcing"]["lane"] == "sourcing"
    assert result["steps"]["external_demand"]["lane"] == "demand"
    assert result["steps"]["playbook_evolution"]["lane"] == "evolution"
    assert result["steps"]["outcome_capture"]["lane"] == "outcomes"
    assert int(result["duration_ms"]) >= 0
