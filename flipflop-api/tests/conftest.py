"""Test fixtures for FlipFlop API tests."""

import pytest
import pytest_asyncio
import inspect
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.main import app
from app.database import get_db


@pytest_asyncio.fixture
async def db(request) -> AsyncSession | Session:
    """Create an isolated session matching the test's execution model."""
    if not inspect.iscoroutinefunction(request.function):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session = Session(engine, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()
            engine.dispose()
        return

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


@pytest.fixture(autouse=True)
def _admin_tests_use_their_isolated_database(request, db):
    """Keep synchronous admin TestClient calls off the configured Postgres DB."""
    if request.module.__name__.endswith("test_admin_dashboard"):
        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            yield
        finally:
            app.dependency_overrides.pop(get_db, None)
    else:
        yield
