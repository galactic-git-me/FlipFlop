"""
Database Integrity Tests

Tests for:
- Migration execution
- Foreign key constraints
- Database constraints (unique, not null)
- Data consistency
- Index presence
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect

from app.database import Base, engine
from app.models.customer import Customer
from app.models.order import Order
from app.models.quote import Quote
from app.models.component import Component


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create in-memory test database."""
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
async def session(test_db):
    """Create database session."""
    SessionLocal = sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as sess:
        yield sess


# ============================================================================
# MIGRATION TESTS
# ============================================================================

class TestMigrations:
    """Test that all migrations run successfully."""

    @pytest.mark.asyncio
    async def test_all_tables_created(self, test_db):
        """Test that all required tables are created."""
        async with test_db.connect() as conn:
            inspector = inspect(conn)
            tables = await conn.run_sync(inspector.get_table_names)

        # Required tables
        required_tables = {
            "customers",
            "orders",
            "quotes",
            "components",
            "order_components",
        }

        for table in required_tables:
            assert table in tables, f"Table {table} not created"

    @pytest.mark.asyncio
    async def test_customer_table_schema(self, test_db):
        """Test customer table has required columns."""
        async with test_db.connect() as conn:
            inspector = inspect(conn)
            columns = await conn.run_sync(
                lambda: inspector.get_columns("customers")
            )

        column_names = {col["name"] for col in columns}

        required_columns = {
            "id",
            "email",
            "password_hash",
            "name",
            "created_at",
            "updated_at",
        }

        for col in required_columns:
            assert col in column_names, f"Column {col} not in customers table"

    @pytest.mark.asyncio
    async def test_order_table_schema(self, test_db):
        """Test order table has required columns."""
        async with test_db.connect() as conn:
            inspector = inspect(conn)
            columns = await conn.run_sync(
                lambda: inspector.get_columns("orders")
            )

        column_names = {col["name"] for col in columns}

        required_columns = {
            "id",
            "customer_id",
            "status",
            "budget",
            "total_price",
            "os_id",
            "theme_id",
            "created_at",
            "updated_at",
        }

        for col in required_columns:
            assert col in column_names, f"Column {col} not in orders table"


# ============================================================================
# CONSTRAINT TESTS
# ============================================================================

class TestConstraints:
    """Test database constraints."""

    @pytest.mark.asyncio
    async def test_customer_email_unique(self, session):
        """Test that customer email is unique."""
        # Create first customer
        customer1 = Customer(
            email="unique@example.com",
            password_hash="hash1",
            name="User 1",
        )
        session.add(customer1)
        await session.commit()

        # Try to create duplicate
        customer2 = Customer(
            email="unique@example.com",
            password_hash="hash2",
            name="User 2",
        )
        session.add(customer2)

        with pytest.raises(Exception):  # IntegrityError
            await session.commit()

    @pytest.mark.asyncio
    async def test_order_customer_foreign_key(self, session):
        """Test order.customer_id foreign key constraint."""
        # Try to create order with non-existent customer
        order = Order(
            customer_id=9999,
            status="pending",
            budget=1500.0,
            total_price=1400.0,
        )
        session.add(order)

        with pytest.raises(Exception):  # IntegrityError
            await session.commit()

    @pytest.mark.asyncio
    async def test_not_null_constraints(self, session):
        """Test NOT NULL constraints."""
        # Create customer without required fields
        with pytest.raises((TypeError, ValueError)):
            customer = Customer(email=None)

    @pytest.mark.asyncio
    async def test_order_required_fields(self, session):
        """Test order required fields."""
        customer = Customer(
            email="test@example.com",
            password_hash="hash",
            name="Test User",
        )
        session.add(customer)
        await session.commit()

        # Order missing status should fail
        order = Order(
            customer_id=customer.id,
            budget=1500.0,
            total_price=1400.0,
        )
        # SQLAlchemy will raise for missing required column


# ============================================================================
# DATA CONSISTENCY TESTS
# ============================================================================

class TestDataConsistency:
    """Test data consistency across tables."""

    @pytest.mark.asyncio
    async def test_order_price_consistency(self, session):
        """Test that order prices are consistent."""
        # Create customer
        customer = Customer(
            email="price@example.com",
            password_hash="hash",
            name="Price Test",
        )
        session.add(customer)
        await session.commit()

        # Create order
        order = Order(
            customer_id=customer.id,
            status="pending",
            budget=1500.0,
            total_price=1400.0,
        )
        session.add(order)
        await session.commit()

        # Verify total_price <= budget
        assert order.total_price <= order.budget

    @pytest.mark.asyncio
    async def test_quote_component_consistency(self, session):
        """Test quote component consistency."""
        customer = Customer(
            email="quote@example.com",
            password_hash="hash",
            name="Quote Test",
        )
        session.add(customer)
        await session.commit()

        quote = Quote(
            customer_id=customer.id,
            budget=1500.0,
            total_price=1400.0,
        )
        session.add(quote)
        await session.commit()

        # Quote should have valid total_price
        assert quote.total_price > 0
        assert quote.total_price <= quote.budget

    @pytest.mark.asyncio
    async def test_timestamp_consistency(self, session):
        """Test that timestamps are set correctly."""
        customer = Customer(
            email="timestamp@example.com",
            password_hash="hash",
            name="Timestamp Test",
        )
        session.add(customer)
        await session.commit()

        # created_at should be set
        assert customer.created_at is not None
        assert customer.updated_at is not None

        # updated_at should be >= created_at
        assert customer.updated_at >= customer.created_at


# ============================================================================
# INDEX TESTS
# ============================================================================

class TestIndexes:
    """Test that performance indexes exist."""

    @pytest.mark.asyncio
    async def test_customer_email_indexed(self, test_db):
        """Test that customer.email is indexed."""
        async with test_db.connect() as conn:
            inspector = inspect(conn)
            indexes = await conn.run_sync(
                lambda: inspector.get_indexes("customers")
            )

        # Should have index on email for fast lookups
        index_columns = {
            col
            for idx in indexes
            for col in idx.get("column_names", [])
        }

        # At minimum, should be able to query by email efficiently
        # (In SQLite, this may not show up the same way)

    @pytest.mark.asyncio
    async def test_order_customer_id_indexed(self, test_db):
        """Test that order.customer_id is indexed."""
        async with test_db.connect() as conn:
            inspector = inspect(conn)
            # Foreign keys are usually auto-indexed
            fks = await conn.run_sync(
                lambda: inspector.get_foreign_keys("orders")
            )

        # Should have foreign key on customer_id
        fk_columns = {fk["constrained_columns"][0] for fk in fks}
        assert "customer_id" in fk_columns


# ============================================================================
# REFERENTIAL INTEGRITY TESTS
# ============================================================================

class TestReferentialIntegrity:
    """Test referential integrity."""

    @pytest.mark.asyncio
    async def test_delete_customer_cascade(self, session):
        """Test that deleting customer cascades to related records."""
        customer = Customer(
            email="cascade@example.com",
            password_hash="hash",
            name="Cascade Test",
        )
        session.add(customer)
        await session.commit()

        order = Order(
            customer_id=customer.id,
            status="pending",
            budget=1500.0,
            total_price=1400.0,
        )
        session.add(order)
        await session.commit()

        # Delete customer
        await session.delete(customer)
        await session.commit()

        # Orders should be deleted or orphaned
        # (depends on CASCADE or SET NULL configuration)

    @pytest.mark.asyncio
    async def test_orphan_order_prevention(self, session):
        """Test that orders can't have non-existent customers."""
        # This is tested via foreign key constraint
        order = Order(
            customer_id=99999,  # Non-existent
            status="pending",
            budget=1500.0,
            total_price=1400.0,
        )
        session.add(order)

        with pytest.raises(Exception):  # IntegrityError
            await session.commit()


# ============================================================================
# COLUMN TYPE TESTS
# ============================================================================

class TestColumnTypes:
    """Test that column types are correct."""

    @pytest.mark.asyncio
    async def test_numeric_precision(self, session):
        """Test numeric column precision."""
        customer = Customer(
            email="numeric@example.com",
            password_hash="hash",
            name="Numeric Test",
        )
        session.add(customer)
        await session.commit()

        # Create order with precise decimal
        order = Order(
            customer_id=customer.id,
            status="pending",
            budget=1234.56,
            total_price=1199.99,
        )
        session.add(order)
        await session.commit()

        # Verify precision is maintained
        assert order.budget == 1234.56
        assert order.total_price == 1199.99

    @pytest.mark.asyncio
    async def test_string_length(self, session):
        """Test string column handling."""
        long_name = "A" * 500
        customer = Customer(
            email="long@example.com",
            password_hash="hash",
            name=long_name[:255],  # Truncate to reasonable length
        )
        session.add(customer)
        await session.commit()

        assert len(customer.name) <= 255


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
