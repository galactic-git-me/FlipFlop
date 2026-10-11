from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from jose import jwt
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.config import get_settings
from app.models.portal_access_grant import PortalAccessGrant
from app.models.manual_build import ManualBuild
from app.api import orders as orders_api
from app.api.orders import (
    PortalGrantCreateIn,
    _guest_manual_grant_matches_build,
    _guest_support_recovery_message,
)
from app.services.portal_access import (
    GUEST_PORTAL_TOKEN_DAYS,
    create_guest_portal_token,
    redeem_claim_secret,
    record_portal_claim_email_result,
)


class CommitRecorder:
    def __init__(self):
        self.commit_count = 0

    async def commit(self):
        self.commit_count += 1


class ClaimLookupResult:
    def __init__(self, grant):
        self.grant = grant

    def scalar_one_or_none(self):
        return self.grant


class ClaimLookupRecorder:
    def __init__(self, grant):
        self.grant = grant
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return ClaimLookupResult(self.grant)

    async def flush(self):
        pass


def test_guest_portal_token_covers_warranty_period_and_is_order_scoped():
    grant = PortalAccessGrant(id=42, order_id=12, manual_build_id=None)

    token = create_guest_portal_token(grant)
    claims = jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[get_settings().jwt_algorithm],
    )

    assert GUEST_PORTAL_TOKEN_DAYS == 400
    assert claims["exp"] - claims["iat"] == 400 * 24 * 60 * 60
    assert claims["grant_id"] == 42
    assert claims["order_id"] == 12
    assert claims["build_id"] is None
    assert claims["scope"] == "portal:read"
    assert claims["capabilities"] == ["support:create"]


@pytest.mark.asyncio
async def test_guest_claim_redemption_locks_the_grant_row():
    grant = SimpleNamespace(
        id=42,
        order_id=12,
        manual_build_id=None,
        revoked=False,
        claimed_at=None,
        expires_at=datetime.utcnow() + timedelta(days=400),
    )
    db = ClaimLookupRecorder(grant)

    redeemed = await redeem_claim_secret(db, "one-time-secret")

    statement = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in statement
    assert redeemed is not None
    assert grant.claimed_at is not None


@pytest.mark.asyncio
async def test_claim_email_success_is_persisted_without_token_url():
    db = CommitRecorder()
    grant = PortalAccessGrant(
        order_id=12,
        contact_email="buyer@example.com",
        token_hash="a" * 64,
        channel="direct_guest",
        email_status="pending",
    )

    await record_portal_claim_email_result(db, grant, sent=True)

    assert grant.email_status == "sent"
    assert isinstance(grant.email_attempted_at, datetime)
    assert grant.email_sent_at == grant.email_attempted_at
    assert not hasattr(grant, "claim_url")
    assert db.commit_count == 1


@pytest.mark.asyncio
async def test_claim_email_failure_is_persisted_without_a_sent_timestamp():
    db = CommitRecorder()
    grant = PortalAccessGrant(
        order_id=13,
        contact_email="buyer@example.com",
        token_hash="b" * 64,
        channel="direct_guest",
        email_status="pending",
    )

    await record_portal_claim_email_result(db, grant, sent=False)

    assert grant.email_status == "failed"
    assert isinstance(grant.email_attempted_at, datetime)
    assert grant.email_sent_at is None
    assert db.commit_count == 1


@pytest.mark.parametrize(
    ("channel", "grant_email", "build_email", "expected"),
    [
        ("ebay", None, None, True),
        ("vinted", None, "buyer@example.com", True),
        ("printed_insert", "buyer@example.com", "buyer@example.com", True),
        ("marketplace", "different@example.com", "buyer@example.com", False),
        ("direct_guest", None, None, False),
        ("unknown", None, None, False),
    ],
)
def test_manual_guest_portal_claim_binding(channel, grant_email, build_email, expected):
    grant = SimpleNamespace(channel=channel, contact_email=grant_email)
    build = SimpleNamespace(customer_email=build_email)

    assert _guest_manual_grant_matches_build(grant, build) is expected


@pytest.mark.parametrize(
    ("channel", "order_id", "expected"),
    [
        ("direct_guest", 123, "verified email on your direct order"),
        ("ebay", None, "through the marketplace you bought from"),
        ("vinted", None, "through the marketplace you bought from"),
    ],
)
def test_guest_support_denial_uses_channel_safe_recovery(channel, order_id, expected):
    grant = SimpleNamespace(channel=channel, order_id=order_id)

    assert expected in _guest_support_recovery_message(grant)
    assert "reissue your verified link" not in _guest_support_recovery_message(grant)


@pytest.mark.asyncio
async def test_marketplace_claim_without_email_creates_private_leaflet_only(db, monkeypatch):
    build = ManualBuild(name="Marketplace PC", status="sold", customer_email=None)
    db.add(build)
    await db.flush()
    leaflet_calls = []

    def create_leaflet(**kwargs):
        leaflet_calls.append(kwargs)
        return {"storage_key": f"{kwargs['build_id']}/leaflet.pdf"}

    monkeypatch.setattr(orders_api, "create_portal_leaflet", create_leaflet)
    monkeypatch.setattr(
        orders_api,
        "get_settings",
        lambda: SimpleNamespace(frontend_url="https://store.example"),
    )

    result = await orders_api.create_portal_access_grant(
        PortalGrantCreateIn(manual_build_id=build.id, contact_email=None, channel="ebay"),
        admin=SimpleNamespace(email="admin@example.com"),
        db=db,
    )

    grant = await db.get(PortalAccessGrant, result["id"])
    assert grant is not None
    assert 399 <= (grant.expires_at - datetime.utcnow()).total_seconds() / 86400 <= 400
    assert grant.contact_email is None
    assert grant.channel == "ebay"
    assert grant.email_status is None
    assert grant.leaflet_storage_key == f"{build.id}/leaflet.pdf"
    assert result["claim_url"] is None
    assert result["email_sent"] is False
    assert "token=" in leaflet_calls[0]["claim_url"]


@pytest.mark.asyncio
async def test_direct_guest_claim_still_requires_verified_email(db):
    with pytest.raises(HTTPException) as error:
        await orders_api.create_portal_access_grant(
            PortalGrantCreateIn(order_id=123, contact_email=None, channel="direct_guest"),
            admin=SimpleNamespace(email="admin@example.com"),
            db=db,
        )

    assert getattr(error.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_portal_claim_expiry_cannot_exceed_warranty_access_window(db):
    with pytest.raises(HTTPException) as error:
        await orders_api.create_portal_access_grant(
            PortalGrantCreateIn(
                manual_build_id=1,
                contact_email=None,
                channel="ebay",
                expires_in_days=401,
            ),
            admin=SimpleNamespace(email="admin@example.com"),
            db=db,
        )

    assert error.value.status_code == 400
