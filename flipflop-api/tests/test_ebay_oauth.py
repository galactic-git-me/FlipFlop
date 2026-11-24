"""
eBay 3-legged seller OAuth. Not verifiable against live eBay (no network
egress to any eBay domain in this environment) — tested against mocked HTTP
responses matching eBay's documented OAuth2 token-endpoint contract.
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401 — registers all models on Base.metadata
from app.services import ebay_oauth

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


def test_build_authorize_url_includes_scopes_and_client_id():
    with patch("app.services.ebay_oauth.get_settings") as mock_settings:
        mock_settings.return_value.ebay_app_id = "test-app-id"
        mock_settings.return_value.ebay_ru_name = "test-ru-name"
        mock_settings.return_value.ebay_environment = "production"
        url = ebay_oauth.build_authorize_url()
    assert "client_id=test-app-id" in url
    assert "redirect_uri=test-ru-name" in url
    assert "auth.ebay.com" in url
    for scope in ebay_oauth.SCOPES:
        assert scope.split("/")[-1] in url


def test_build_authorize_url_uses_sandbox_host():
    with patch("app.services.ebay_oauth.get_settings") as mock_settings:
        mock_settings.return_value.ebay_app_id = "x"
        mock_settings.return_value.ebay_ru_name = "y"
        mock_settings.return_value.ebay_environment = "sandbox"
        url = ebay_oauth.build_authorize_url()
    assert "auth.sandbox.ebay.com" in url


async def test_exchange_code_for_tokens_success():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {
        "access_token": "AT-123", "expires_in": 7200,
        "refresh_token": "RT-456", "refresh_token_expires_in": 47304000,
        "scope": "sell.inventory",
    }
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        with patch("app.services.ebay_oauth.get_settings") as mock_settings:
            mock_settings.return_value.ebay_app_id = "id"
            mock_settings.return_value.ebay_client_secret = "secret"
            mock_settings.return_value.ebay_ru_name = "ru"
            mock_settings.return_value.ebay_environment = "production"
            payload = await ebay_oauth.exchange_code_for_tokens("some-code")

    assert payload["access_token"] == "AT-123"
    assert payload["refresh_token"] == "RT-456"


async def test_exchange_code_for_tokens_failure_raises():
    mock_resp = AsyncMock()
    mock_resp.status_code = 400
    mock_resp.text = "invalid_grant"
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        with patch("app.services.ebay_oauth.get_settings") as mock_settings:
            mock_settings.return_value.ebay_app_id = "id"
            mock_settings.return_value.ebay_client_secret = "secret"
            mock_settings.return_value.ebay_ru_name = "ru"
            mock_settings.return_value.ebay_environment = "production"
            with pytest.raises(ebay_oauth.EbayOAuthError):
                await ebay_oauth.exchange_code_for_tokens("bad-code")


async def test_store_and_get_valid_token_roundtrip(db_session):
    from app.models.app_settings import AppSettings
    from sqlalchemy import select

    payload = {
        "access_token": "AT-1", "expires_in": 7200,
        "refresh_token": "RT-1", "refresh_token_expires_in": 47304000,
        "scope": "sell.inventory sell.account",
    }
    await ebay_oauth.store_tokens_from_exchange(db_session, payload)
    await db_session.commit()

    row = (await db_session.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one()
    assert row.ebay_seller_access_token.startswith("enc:v1:")
    assert row.ebay_seller_refresh_token.startswith("enc:v1:")
    assert "AT-1" not in row.ebay_seller_access_token
    assert "RT-1" not in row.ebay_seller_refresh_token

    token = await ebay_oauth.get_valid_access_token(db_session)
    assert token == "AT-1"

    status = await ebay_oauth.get_connection_status(db_session)
    assert status["connected"] is True
    assert "sell.inventory" in status["scopes"]


async def test_get_valid_access_token_none_when_never_connected(db_session):
    token = await ebay_oauth.get_valid_access_token(db_session)
    assert token is None
    status = await ebay_oauth.get_connection_status(db_session)
    assert status["connected"] is False


async def test_get_valid_access_token_auto_refreshes_when_expired(db_session):
    from app.models.app_settings import AppSettings

    row = AppSettings(
        name="default",
        ebay_seller_access_token="AT-old",
        ebay_seller_access_token_expires_at=datetime.utcnow() - timedelta(minutes=1),
        ebay_seller_refresh_token="RT-1",
        ebay_seller_refresh_token_expires_at=datetime.utcnow() + timedelta(days=300),
        ebay_seller_connected_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(row)
    await db_session.commit()

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"access_token": "AT-new", "expires_in": 7200}
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        with patch("app.services.ebay_oauth.get_settings") as mock_settings:
            mock_settings.return_value.ebay_app_id = "id"
            mock_settings.return_value.ebay_client_secret = "secret"
            mock_settings.return_value.ebay_token_encryption_key = "test-encryption-key"
            token = await ebay_oauth.get_valid_access_token(db_session)

    assert token == "AT-new"
    assert row.ebay_seller_access_token.startswith("enc:v1:")
    assert row.ebay_seller_refresh_token.startswith("enc:v1:")


async def test_plaintext_token_is_migrated_on_read(db_session):
    from app.models.app_settings import AppSettings

    row = AppSettings(
        name="default",
        ebay_seller_access_token="legacy-access-token",
        ebay_seller_access_token_expires_at=datetime.utcnow() + timedelta(hours=1),
        ebay_seller_refresh_token="legacy-refresh-token",
        ebay_seller_refresh_token_expires_at=datetime.utcnow() + timedelta(days=300),
    )
    db_session.add(row)
    await db_session.commit()

    assert await ebay_oauth.get_valid_access_token(db_session) == "legacy-access-token"
    assert row.ebay_seller_access_token.startswith("enc:v1:")


async def test_get_valid_access_token_none_when_refresh_token_expired(db_session):
    from app.models.app_settings import AppSettings

    row = AppSettings(
        name="default",
        ebay_seller_access_token="AT-old",
        ebay_seller_access_token_expires_at=datetime.utcnow() - timedelta(days=1),
        ebay_seller_refresh_token="RT-1",
        ebay_seller_refresh_token_expires_at=datetime.utcnow() - timedelta(days=1),
        ebay_seller_connected_at=datetime.utcnow() - timedelta(days=400),
    )
    db_session.add(row)
    await db_session.commit()

    token = await ebay_oauth.get_valid_access_token(db_session)
    assert token is None


async def test_disconnect_clears_tokens(db_session):
    payload = {"access_token": "AT-1", "expires_in": 7200, "refresh_token": "RT-1", "refresh_token_expires_in": 1000}
    await ebay_oauth.store_tokens_from_exchange(db_session, payload)
    await db_session.commit()

    await ebay_oauth.disconnect(db_session)
    await db_session.commit()

    status = await ebay_oauth.get_connection_status(db_session)
    assert status["connected"] is False
