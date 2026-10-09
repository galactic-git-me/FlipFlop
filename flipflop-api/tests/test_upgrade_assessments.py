import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.customer import Customer
from app.models.upgrade_assessment import UpgradeAssessment
from app.api.upgrades import UpgradeAdvice, UpgradeIntake, approve_scope, get_upgrade, publish_advice, submit_upgrade


@pytest.mark.asyncio
async def test_keep_advice_and_material_change_approval_are_customer_scoped():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Customer.__table__.create)
        await connection.run_sync(UpgradeAssessment.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        owner = Customer(email="owner@example.test", name="Owner")
        stranger = Customer(email="stranger@example.test", name="Stranger")
        db.add_all([owner, stranger])
        await db.commit()
        created = await submit_upgrade(UpgradeIntake(desired_outcome="Keep my current PC useful", budget_gbp=500), owner, db)
        assessment_id = created["id"]
        with pytest.raises(HTTPException) as exc:
            await get_upgrade(assessment_id, stranger, db)
        assert exc.value.status_code == 404
        advised = await publish_advice(assessment_id, UpgradeAdvice(
            recommendation="KEEP", explanation="Your current machine already meets the stated workload.",
        ), db)
        assert advised["advice"]["recommendation"] == "KEEP"
        assert advised["approval_required"] is False
        changed = await publish_advice(assessment_id, UpgradeAdvice(
            recommendation="TRANSFORM", explanation="Physical inspection found a case clearance issue.",
            material_change=True, quoted_price_gbp=300,
        ), db)
        assert changed["approval_required"] is True
        with pytest.raises(HTTPException):
            await approve_scope(assessment_id, stranger, db)
        approved = await approve_scope(assessment_id, owner, db)
        assert approved["approved_revision"] == changed["scope_revision"]
    await engine.dispose()
