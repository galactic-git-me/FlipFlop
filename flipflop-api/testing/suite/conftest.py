"""Test fixtures for FlipFlop API tests."""

import os
import socket
from uuid import UUID

import psycopg2
from sqlalchemy.engine import make_url

# Some integration and worker tests import the application's module-level
# AsyncSessionLocal directly. Always bind that engine to the database created
# by scripts/run_isolated_tests.py before importing app.database or app.main.
_test_database_url = os.environ.get("FLIPFLOP_TEST_DATABASE_URL", "")
if not _test_database_url:
    raise RuntimeError(
        "Tests must run through scripts/run_isolated_tests.py, which creates a "
        "unique disposable PostgreSQL database and applies the migration chain."
    )
_test_url = make_url(_test_database_url)
_test_database_name = _test_url.database or ""
if (
    _test_url.drivername != "postgresql+asyncpg"
    or not _test_database_name.startswith("flipflop_test_")
    or not _test_database_name.endswith("_test")
    or _test_url.host not in {"127.0.0.1", "localhost", "::1"}
):
    raise RuntimeError(
        "FLIPFLOP_TEST_DATABASE_URL must target a uniquely named "
        "flipflop_test_*_test PostgreSQL database."
    )
_test_run_token = os.environ.get("FLIPFLOP_TEST_RUN_TOKEN", "")
try:
    UUID(_test_run_token)
except ValueError as error:
    raise RuntimeError("Tests must use a database created by scripts/run_isolated_tests.py") from error
os.environ["DATABASE_URL"] = _test_database_url
os.environ["TEST_DATABASE_URL"] = _test_database_url
os.environ["SYNC_DATABASE_URL"] = _test_url.set(drivername="postgresql").render_as_string(hide_password=False)


def pytest_sessionstart(session) -> None:
    """Permit test traffic only to the isolated PostgreSQL endpoint."""
    sync_url = _test_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg2.connect(sync_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT run_token FROM flipflop_test_run_marker")
            marker = cursor.fetchone()
    if not marker or str(marker[0]) != _test_run_token:
        raise RuntimeError("Disposable database marker is missing or does not match this test run")

    allowed_hosts = {"localhost", "127.0.0.1", "::1"}
    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        if host not in allowed_hosts:
            raise RuntimeError(f"Outbound network is disabled in tests (host: {host})")
        return original_getaddrinfo(host, port, *args, **kwargs)

    def is_test_database_address(address) -> bool:
        return (
            isinstance(address, tuple)
            and len(address) >= 2
            and address[0] in allowed_hosts
        )

    def guarded_connect(sock, address):
        if not is_test_database_address(address):
            raise RuntimeError(f"Non-loopback network is disabled in tests (address: {address!r})")
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if not is_test_database_address(address):
            raise RuntimeError(f"Non-loopback network is disabled in tests (address: {address!r})")
        return original_connect_ex(sock, address)

    socket.getaddrinfo = guarded_getaddrinfo
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    session.config._flipflop_original_socket_methods = (
        original_getaddrinfo,
        original_connect,
        original_connect_ex,
    )


def pytest_sessionfinish(session, exitstatus) -> None:
    originals = getattr(session.config, "_flipflop_original_socket_methods", None)
    if originals:
        socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex = originals

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
        class AsyncSessionAdapter:
            """Expose the sync fixture session through the async route contract."""

            def __init__(self, session):
                self.session = session

            async def execute(self, *args, **kwargs):
                return self.session.execute(*args, **kwargs)

            async def get(self, *args, **kwargs):
                return self.session.get(*args, **kwargs)

            class _Completed:
                def __await__(self):
                    if False:
                        yield None
                    return None

            def commit(self):
                self.session.commit()
                return self._Completed()

            def refresh(self, *args, **kwargs):
                self.session.refresh(*args, **kwargs)
                return self._Completed()

            async def flush(self):
                self.session.flush()

            async def run_sync(self, callback):
                return callback(self.session)

            def add(self, instance):
                self.session.add(instance)

            def __getattr__(self, name):
                return getattr(self.session, name)

        async def override_get_db():
            yield AsyncSessionAdapter(db)

        app.dependency_overrides[get_db] = override_get_db
        try:
            yield
        finally:
            app.dependency_overrides.pop(get_db, None)
    else:
        yield
