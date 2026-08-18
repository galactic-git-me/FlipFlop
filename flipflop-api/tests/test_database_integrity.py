"""Integrity checks for the current customer, order and quote contracts."""

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.services.quote_service import QuoteService

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(test_db):
    factory = sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db


def make_order(customer_id: int, suffix: str = "1", price: float = 1400.0) -> Order:
    return Order(
        order_id=f"test-order-{suffix}", customer_id=customer_id,
        specs={"cpu": "Ryzen 7", "gpu": "RTX 4070"},
        customer_price=price, component_costs=1100.0,
        overhead_amount=100.0, status=OrderStatus.AWAITING_SOURCING,
    )


@pytest.mark.asyncio
async def test_current_core_tables_and_order_columns_exist(test_db):
    async with test_db.connect() as connection:
        tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        columns = await connection.run_sync(
            lambda sync: {column["name"] for column in inspect(sync).get_columns("orders")}
        )
    assert {"customers", "orders", "component_catalogue"}.issubset(tables)
    assert {"order_id", "customer_id", "specs", "customer_price",
            "component_costs", "overhead_amount", "status"}.issubset(columns)


@pytest.mark.asyncio
async def test_customer_email_is_unique(session):
    session.add(Customer(email="unique@example.com", password_hash="one", name="One"))
    await session.commit()
    session.add(Customer(email="unique@example.com", password_hash="two", name="Two"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_order_requires_a_real_customer(session):
    session.add(make_order(999999))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_order_round_trip_preserves_current_economics(session):
    customer = Customer(email="order@example.com", password_hash="hash", name="Order")
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
async def test_customer_email_and_order_id_are_indexed(test_db):
    async with test_db.connect() as connection:
        customer_indexes = await connection.run_sync(lambda sync: inspect(sync).get_indexes("customers"))
        order_indexes = await connection.run_sync(lambda sync: inspect(sync).get_indexes("orders"))
    assert any("email" in index["column_names"] for index in customer_indexes)
    assert any("order_id" in index["column_names"] for index in order_indexes)
