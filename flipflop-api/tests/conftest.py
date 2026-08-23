"""Test fixtures for FlipFlop API tests."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
from app.database import Base


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Create a test database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = AsyncSession(engine, expire_on_commit=False)

    yield async_session

    await async_session.close()
    await engine.dispose()
