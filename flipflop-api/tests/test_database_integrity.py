"""Integrity checks for the current customer, order and quote contracts."""

import asyncio
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app import main as _main  # noqa: F401 - registers every FK target in Base metadata
from app.database import Base
from app.models.customer import Customer
from app.models.customer_problem import CustomerProblem
from app.models.getting_started_job import GettingStartedJob
from app.models.manual_build import ManualBuild
from app.models.order import Order, OrderStatus
from app.models.warranty import WarrantyClaim, WarrantyReserve
from app.api import orders as orders_api
from app.api.orders import WarrantyReleaseIn
from app.services.getting_started_jobs import lock_manual_build_then_getting_started_job
from app.services.quote_service import QuoteService
from app.services.warranty_service import lock_warranty_reserve_then_claim

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://flipper:flipper@127.0.0.1:5432/pcflipper",
)
TEST_DATABASE_SCHEMA = os.getenv("TEST_DATABASE_SCHEMA", "flipflop_test")


def assert_isolated_postgres_target(url: str, schema: str) -> None:
    database = make_url(url).database or ""
    isolated_database = database.endswith("_test")
    isolated_schema = schema == "flipflop_test"
    if not url.startswith("postgresql+asyncpg://") or not (isolated_database or isolated_schema):
        raise RuntimeError(
            "Integrity tests require PostgreSQL plus either a database ending "
            "in '_test' or the dedicated 'flipflop_test' schema."
        )


@pytest.fixture
async def test_db():
    assert_isolated_postgres_target(TEST_DATABASE_URL, TEST_DATABASE_SCHEMA)
    engine = create_async_engine(
        TEST_DATABASE_URL,
        execution_options={"schema_translate_map": {None: TEST_DATABASE_SCHEMA}},
    )
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_DATABASE_SCHEMA}"'))
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(test_db):
    async with test_db.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as db:
            yield db
        await transaction.rollback()


def make_order(customer_id: int, suffix: str | None = None, price: float = 1400.0) -> Order:
    return Order(
        order_id=f"test-order-{suffix or uuid4().hex}", customer_id=customer_id,
        specs={"cpu": "Ryzen 7", "gpu": "RTX 4070"},
        customer_price=price, component_costs=1100.0,
        overhead_amount=100.0, status=OrderStatus.AWAITING_SOURCING,
    )


async def _wait_until_postgres_backend_is_lock_blocked(engine, pid: int) -> bool:
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sessions() as observer:
        for _ in range(200):
            wait_event = await observer.scalar(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                {"pid": pid},
            )
            if wait_event == "Lock":
                return True
            await asyncio.sleep(0.01)
    return False


@pytest.mark.asyncio
async def test_current_core_tables_and_order_columns_exist(test_db):
    async with test_db.connect() as connection:
        tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names(schema=TEST_DATABASE_SCHEMA))
        columns = await connection.run_sync(
            lambda sync: {column["name"] for column in inspect(sync).get_columns("orders", schema=TEST_DATABASE_SCHEMA)}
        )
    assert {"customers", "orders", "component_catalogue"}.issubset(tables)
    assert {"order_id", "customer_id", "specs", "customer_price",
            "component_costs", "overhead_amount", "status"}.issubset(columns)


@pytest.mark.asyncio
async def test_customer_email_is_unique(session):
    email = f"unique-{uuid4().hex}@example.com"
    session.add(Customer(email=email, password_hash="one", name="One"))
    await session.commit()
    session.add(Customer(email=email, password_hash="two", name="Two"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_order_requires_a_real_customer(session):
    session.add(make_order(999999))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_order_round_trip_preserves_current_economics(session):
    customer = Customer(email=f"order-{uuid4().hex}@example.com", password_hash="hash", name="Order")
    session.add(customer)
    await session.flush()
    order = make_order(customer.id, price=1234.56)
    session.add(order)
    await session.commit()
    assert order.customer_price == 1234.56
    assert order.component_costs + order.overhead_amount < order.customer_price
    assert order.specs["gpu"] == "RTX 4070"


@pytest.mark.asyncio
async def test_quote_calculation_is_positive_and_within_budget(session):
    quote = await QuoteService.generate_quote(1500.0, session)
    assert quote is not None
    assert quote["parts_cost_total"] > 0
    assert 0 < quote["total_price"] <= quote["budget"]
    assert quote["within_budget"] is True
    assert len(quote["components"]) == 8


@pytest.mark.asyncio
async def test_warranty_claim_lock_waits_for_reserve_lock_on_postgres(test_db):
    """A second claim writer must wait while another transaction owns the reserve lock."""
    async with AsyncSession(test_db, expire_on_commit=False) as setup:
        customer = Customer(
            email=f"warranty-lock-{uuid4().hex}@example.com",
            name="Warranty Lock Test",
        )
        setup.add(customer)
        await setup.flush()
        order = make_order(customer.id, suffix=f"warranty-lock-{uuid4().hex}")
        setup.add(order)
        await setup.flush()
        problem = CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty_claim",
            description="Synthetic concurrency fixture",
        )
        setup.add(problem)
        await setup.flush()
        reserve = WarrantyReserve(
            order_id=order.id,
            sale_value_gbp=order.customer_price,
            reserve_pct=5.0,
            reserved_amount_gbp=round(order.customer_price * 0.05, 2),
            warranty_started_at=datetime(2026, 1, 1),
            warranty_expires_at=datetime(2027, 1, 1),
        )
        setup.add(reserve)
        await setup.flush()
        claim = WarrantyClaim(
            reserve_id=reserve.id,
            customer_problem_id=problem.id,
            issue_summary=problem.description,
            status="open",
        )
        setup.add(claim)
        await setup.commit()
        claim_id = claim.id

    sessions = async_sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
    lock_owner = sessions()
    competing_writer_pid = asyncio.get_running_loop().create_future()

    async def competing_writer():
        async with sessions() as writer:
            pid = await writer.scalar(text("SELECT pg_backend_pid()"))
            competing_writer_pid.set_result(int(pid))
            locked_reserve, locked_claim = await lock_warranty_reserve_then_claim(writer, claim_id)
            return locked_reserve.id, locked_claim.id

    waiter = None
    try:
        reserve, claim = await lock_warranty_reserve_then_claim(lock_owner, claim_id)
        assert reserve is not None and claim is not None
        waiter = asyncio.create_task(competing_writer())
        competing_pid = await asyncio.wait_for(competing_writer_pid, timeout=5)
        assert await _wait_until_postgres_backend_is_lock_blocked(test_db, competing_pid), (
            "The competing claim writer did not wait on the reserved row lock"
        )

        await lock_owner.commit()
        assert await asyncio.wait_for(waiter, timeout=5) == (reserve.id, claim.id)
    finally:
        await lock_owner.rollback()
        if waiter is not None:
            if not waiter.done():
                waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
        await lock_owner.close()


@pytest.mark.asyncio
async def test_getting_ready_writer_waits_on_build_before_locking_job(test_db):
    """A competing preparation writer serializes on the physical build row."""
    async with AsyncSession(test_db, expire_on_commit=False) as setup:
        build = ManualBuild(name=f"Getting Ready lock {uuid4().hex}")
        setup.add(build)
        await setup.flush()
        job = GettingStartedJob(
            manual_build_id=build.id,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            checklist={},
            customer_software_selections=[],
            purchased_ai_services=[],
            artifact_index=[],
        )
        setup.add(job)
        await setup.commit()
        build_id = build.id

    sessions = async_sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
    lock_owner = sessions()
    competing_writer_pid = asyncio.get_running_loop().create_future()

    async def competing_writer():
        async with sessions() as writer:
            pid = await writer.scalar(text("SELECT pg_backend_pid()"))
            competing_writer_pid.set_result(int(pid))
            locked_build, locked_job = await lock_manual_build_then_getting_started_job(writer, build_id)
            await writer.commit()
            return locked_build.id, locked_job.id

    waiter = None
    try:
        locked_build, locked_job = await lock_manual_build_then_getting_started_job(lock_owner, build_id)
        assert locked_build is not None and locked_job is not None
        waiter = asyncio.create_task(competing_writer())
        competing_pid = await asyncio.wait_for(competing_writer_pid, timeout=5)
        assert await _wait_until_postgres_backend_is_lock_blocked(test_db, competing_pid), (
            "The competing Getting Ready writer did not wait on the physical build row"
        )

        await lock_owner.commit()
        assert await asyncio.wait_for(waiter, timeout=5) == (locked_build.id, locked_job.id)
    finally:
        await lock_owner.rollback()
        if waiter is not None:
            if not waiter.done():
                waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
        await lock_owner.close()


@pytest.mark.asyncio
async def test_reserve_attachment_waits_for_existing_case_update_and_uses_latest_status(test_db):
    """Delivery-time reserve attachment must snapshot the case after its row lock."""
    async with AsyncSession(test_db, expire_on_commit=False) as setup:
        customer = Customer(
            email=f"warranty-attach-{uuid4().hex}@example.com",
            name="Warranty Attachment Test",
        )
        setup.add(customer)
        await setup.flush()
        order = make_order(customer.id, suffix=f"warranty-attach-{uuid4().hex}")
        setup.add(order)
        await setup.flush()
        problem = CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty_claim",
            description="Synthetic pre-delivery report",
            status="return_in_transit",
        )
        setup.add(problem)
        await setup.flush()
        reserve = WarrantyReserve(
            order_id=order.id,
            sale_value_gbp=order.customer_price,
            reserve_pct=5.0,
            reserved_amount_gbp=round(order.customer_price * 0.05, 2),
            warranty_started_at=datetime(2026, 1, 1),
            warranty_expires_at=datetime(2027, 1, 1),
        )
        setup.add(reserve)
        await setup.commit()
        order_id, problem_id = order.id, problem.id

    sessions = async_sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
    case_writer = sessions()
    competing_attacher_pid = asyncio.get_running_loop().create_future()

    async def attach_reserve_case():
        async with sessions() as attacher:
            pid = await attacher.scalar(text("SELECT pg_backend_pid()"))
            competing_attacher_pid.set_result(int(pid))
            order = await attacher.get(Order, order_id)
            reserve = await ensure_order_reserve(attacher, order, datetime(2026, 1, 1))
            reserve_id = reserve.id
            await attacher.commit()
            return reserve_id

    attacher_task = None
    try:
        problem = await case_writer.get(CustomerProblem, problem_id, with_for_update=True)
        problem.status = "received_for_inspection"
        attacher_task = asyncio.create_task(attach_reserve_case())
        attacher_pid = await asyncio.wait_for(competing_attacher_pid, timeout=5)
        assert await _wait_until_postgres_backend_is_lock_blocked(test_db, attacher_pid), (
            "Reserve attachment did not wait for the existing case update"
        )

        await case_writer.commit()
        attached_reserve = await asyncio.wait_for(attacher_task, timeout=5)
        async with sessions() as verify:
            claim = (await verify.execute(
                select(WarrantyClaim).where(WarrantyClaim.customer_problem_id == problem_id)
            )).scalar_one()
            assert claim.reserve_id == attached_reserve
            assert claim.status == "received_for_inspection"
    finally:
        await case_writer.rollback()
        if attacher_task is not None:
            if not attacher_task.done():
                attacher_task.cancel()
            await asyncio.gather(attacher_task, return_exceptions=True)
        await case_writer.close()


@pytest.mark.asyncio
async def test_claim_submission_serializes_with_explicit_reserve_release(test_db, monkeypatch):
    """A flushed warranty case must be attached before release can evaluate claims."""
    async with AsyncSession(test_db, expire_on_commit=False) as setup:
        customer = Customer(
            email=f"warranty-release-race-{uuid4().hex}@example.com",
            name="Warranty Release Race",
        )
        setup.add(customer)
        await setup.flush()
        order = make_order(customer.id, suffix=f"warranty-release-race-{uuid4().hex}")
        setup.add(order)
        await setup.flush()
        now = datetime.utcnow()
        reserve = WarrantyReserve(
            order_id=order.id,
            sale_value_gbp=order.customer_price,
            reserve_pct=5.0,
            reserved_amount_gbp=round(order.customer_price * 0.05, 2),
            warranty_started_at=now - timedelta(days=366),
            warranty_expires_at=now - timedelta(days=1),
            status="held",
        )
        setup.add(reserve)
        await setup.commit()
        order_id, customer_id, reserve_id = order.id, customer.id, reserve.id

    sessions = async_sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
    case_db = sessions()
    case_flushed = asyncio.Event()
    allow_reserve_attachment = asyncio.Event()
    release_pid_future = asyncio.get_running_loop().create_future()
    original_ensure_order_reserve = orders_api.ensure_order_reserve

    async def pause_after_case_flush(db, order, started_at):
        case_flushed.set()
        await allow_reserve_attachment.wait()
        return await original_ensure_order_reserve(db, order, started_at)

    monkeypatch.setattr(orders_api, "ensure_order_reserve", pause_after_case_flush)

    async def create_claiming_case():
        order = await case_db.get(Order, order_id)
        problem = await orders_api._create_customer_problem(
            case_db,
            order=order,
            build=None,
            customer_id=customer_id,
            grant=None,
            category="warranty_claim",
            description="The PC no longer starts reliably.",
        )
        await case_db.commit()
        return problem.id

    async def attempt_release():
        async with sessions() as release_db:
            pid = await release_db.scalar(text("SELECT pg_backend_pid()"))
            release_pid_future.set_result(int(pid))
            try:
                await orders_api.release_warranty_reserve(
                    reserve_id,
                    WarrantyReleaseIn(confirm_release=True, note="Reviewed expiry"),
                    SimpleNamespace(email="admin@example.com"),
                    release_db,
                )
            except HTTPException as error:
                await release_db.rollback()
                return error.status_code
            await release_db.commit()
            return 200

    case_task = None
    release_task = None
    try:
        case_task = asyncio.create_task(create_claiming_case())
        await asyncio.wait_for(case_flushed.wait(), timeout=5)
        release_task = asyncio.create_task(attempt_release())
        release_pid = await asyncio.wait_for(release_pid_future, timeout=5)
        assert await _wait_until_postgres_backend_is_lock_blocked(test_db, release_pid), (
            "Reserve release did not wait for the in-flight warranty case transaction"
        )

        allow_reserve_attachment.set()
        problem_id = await asyncio.wait_for(case_task, timeout=5)
        assert await asyncio.wait_for(release_task, timeout=5) == 409

        async with sessions() as verify:
            persisted_problem = await verify.get(CustomerProblem, problem_id)
            persisted_reserve = await verify.get(WarrantyReserve, reserve_id)
            claim = (await verify.execute(
                select(WarrantyClaim).where(WarrantyClaim.customer_problem_id == problem_id)
            )).scalar_one()
            assert persisted_problem is not None
            assert claim.status == "open"
            assert claim.reserve_id == reserve_id
            assert persisted_reserve.status == "claim_open"
            assert persisted_reserve.released_at is None
    finally:
        allow_reserve_attachment.set()
        await case_db.rollback()
        for task in (case_task, release_task):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (case_task, release_task) if task is not None),
            return_exceptions=True,
        )
        await case_db.close()


@pytest.mark.asyncio
async def test_customer_email_and_order_id_are_indexed(test_db):
    async with test_db.connect() as connection:
        customer_indexes = await connection.run_sync(lambda sync: inspect(sync).get_indexes("customers", schema=TEST_DATABASE_SCHEMA))
        order_indexes = await connection.run_sync(lambda sync: inspect(sync).get_indexes("orders", schema=TEST_DATABASE_SCHEMA))
    assert any("email" in index["column_names"] for index in customer_indexes)
    assert any("order_id" in index["column_names"] for index in order_indexes)
