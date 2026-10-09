"""Verify concurrent workshop holds against an isolated local Postgres test DB.

Set TEST_DATABASE_URL to a localhost database whose name ends in ``_test``.
The script creates and removes a unique schema inside that database.
"""
import asyncio
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.commerce_intelligence import (
    ReleaseCapacityRequest, ReserveCapacityRequest, WorkshopCapacityEvidenceInput,
    capture_workshop_capacity, release_workshop_capacity, reserve_workshop_capacity,
)
from app.database import Base
from app.models.commerce_evidence import (
    PriceQuoteSnapshot, SupplierOfferEvidence, WorkshopCapacityEvidence,
    WorkshopCapacityReservation, WorkshopCapacityReservationEvent,
)


async def main() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    target = make_url(url)
    if target.host not in {"127.0.0.1", "localhost"} or not (target.database or "").endswith("_test"):
        raise RuntimeError("Use an isolated localhost Postgres database ending in _test")
    schema = "capacity_check_" + uuid4().hex[:12]
    engine = create_async_engine(url, execution_options={"schema_translate_map": {None: schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tables = [
        SupplierOfferEvidence.__table__, PriceQuoteSnapshot.__table__, WorkshopCapacityEvidence.__table__,
        WorkshopCapacityReservation.__table__, WorkshopCapacityReservationEvent.__table__,
    ]
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(Base.metadata.create_all, tables=tables)

        now = datetime.now(timezone.utc)
        iso = now.date().isocalendar()
        week = f"{iso.year}-W{iso.week:02d}"
        async with sessions() as db:
            capacity = WorkshopCapacityEvidence(
                build_week=week, available_builds=1, observed_at=now,
                evidence_source="isolated-check", evidence_ref="local-test",
                captured_by_admin_id=1, captured_at=now,
            )
            db.add(capacity)
            await db.flush()
            snapshots = [PriceQuoteSnapshot(
                product_key=f"check-{index}", status="offerable",
                evidence_json={
                    "workshop_capacity": {"id": capacity.id, "build_week": week},
                    "request": {"market": {"observed_at": now.isoformat()}},
                    "supplier_offers": [{"stock_confirmed": True, "observed_at": now.isoformat()}],
                },
                decision_json={"offerable": True}, created_by_admin_id=1, created_at=now,
            ) for index in range(2)]
            db.add_all(snapshots)
            await db.commit()
            snapshot_ids = [snapshot.id for snapshot in snapshots]

        admin = SimpleNamespace(id=1)

        async def hold(snapshot_id: int):
            async with sessions() as db:
                try:
                    return await reserve_workshop_capacity(ReserveCapacityRequest(quote_snapshot_id=snapshot_id), db, admin)
                except HTTPException as exc:
                    return exc

        results = await asyncio.gather(*(hold(snapshot_id) for snapshot_id in snapshot_ids))
        held = [result for result in results if isinstance(result, dict)]
        rejected = [result for result in results if isinstance(result, HTTPException)]
        assert len(held) == 1 and len(rejected) == 1 and rejected[0].status_code == 409, results

        winner_id = snapshot_ids[0] if isinstance(results[0], dict) else snapshot_ids[1]
        repeated = await hold(winner_id)
        assert isinstance(repeated, dict) and repeated["id"] == held[0]["id"], repeated

        async with sessions() as db:
            count = await db.scalar(select(func.count(WorkshopCapacityReservation.id)))
            assert count == 1, count
            released = await release_workshop_capacity(
                held[0]["id"], ReleaseCapacityRequest(reason="isolated concurrency check"), db, admin,
            )
            assert released["status"] == "released", released

        ended = await hold(winner_id)
        assert isinstance(ended, HTTPException) and ended.status_code == 409, ended

        loser_id = snapshot_ids[0] if results[0] is rejected[0] else snapshot_ids[1]
        second_hold = await hold(loser_id)
        assert isinstance(second_hold, dict) and second_hold["status"] == "held", second_hold
        async with sessions() as db:
            event_count = await db.scalar(select(func.count(WorkshopCapacityReservationEvent.id)))
            assert event_count == 3, event_count
            stale_snapshot = PriceQuoteSnapshot(
                product_key="stale-capacity", status="offerable",
                evidence_json={
                    "workshop_capacity": {"id": capacity.id, "build_week": week},
                    "request": {"market": {"observed_at": now.isoformat()}},
                    "supplier_offers": [{"stock_confirmed": True, "observed_at": now.isoformat()}],
                },
                decision_json={"offerable": True}, created_by_admin_id=1, created_at=now,
            )
            db.add(stale_snapshot)
            await db.commit()
            stale_snapshot_id = stale_snapshot.id

        async with sessions() as db:
            await capture_workshop_capacity(
                WorkshopCapacityEvidenceInput(
                    build_week=week, available_builds=0, observed_at=datetime.now(timezone.utc),
                    evidence_source="isolated-check", evidence_ref="closed-week",
                ),
                db, admin,
            )
        superseded = await hold(stale_snapshot_id)
        assert isinstance(superseded, HTTPException) and superseded.status_code == 409, superseded
        async with sessions() as db:
            revoked = await db.get(WorkshopCapacityReservation, second_hold["id"])
            event_count = await db.scalar(select(func.count(WorkshopCapacityReservationEvent.id)))
            assert revoked.status == "released" and event_count == 4, (revoked.status, event_count)
        print("PASS: concurrent limit, idempotent retry, release, audit events, capacity reduction")
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
