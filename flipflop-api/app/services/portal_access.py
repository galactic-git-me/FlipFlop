from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.portal_access_grant import PortalAccessGrant
from app.models.getting_started_job import GettingStartedJob
from app.models.order import Order
from app.services.getting_ready_package import create_portal_leaflet

GUEST_PORTAL_TOKEN_DAYS = 400


def _hash_claim_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def new_claim_secret() -> tuple[str, str]:
    secret = secrets.token_urlsafe(32)
    return secret, _hash_claim_secret(secret)


async def find_printable_portal_claim(
    db: AsyncSession,
    *,
    order_id: int | None = None,
    manual_build_id: int | None = None,
    channel: str | None = None,
    include_claimed: bool = False,
) -> PortalAccessGrant | None:
    """Find a current private QR grant without rotating or exposing its secret."""
    if (order_id is None) == (manual_build_id is None):
        raise ValueError("Provide exactly one portal claim owner")
    now = datetime.utcnow()
    query = select(PortalAccessGrant).where(
        PortalAccessGrant.revoked.is_(False),
        PortalAccessGrant.leaflet_storage_key.is_not(None),
    )
    query = query.where(PortalAccessGrant.order_id == order_id) if order_id is not None else query.where(
        PortalAccessGrant.manual_build_id == manual_build_id
    )
    if channel:
        query = query.where(PortalAccessGrant.channel == channel)
    if include_claimed:
        query = query.where(or_(
            and_(PortalAccessGrant.claimed_at.is_(None), PortalAccessGrant.expires_at > now),
            PortalAccessGrant.claimed_at.is_not(None),
        ))
    else:
        query = query.where(PortalAccessGrant.claimed_at.is_(None), PortalAccessGrant.expires_at > now)
    return (await db.execute(query.order_by(PortalAccessGrant.created_at.desc(), PortalAccessGrant.id.desc()).limit(1))).scalar_one_or_none()


def create_guest_portal_token(
    grant: PortalAccessGrant, *, days: int = GUEST_PORTAL_TOKEN_DAYS,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "typ": "guest_portal",
        "scope": "portal:read",
        "capabilities": ["support:create"],
        "grant_id": grant.id,
        "order_id": grant.order_id,
        "build_id": grant.manual_build_id,
        "iat": now,
        "exp": now + timedelta(days=days),
    }
    settings = get_settings()
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


async def redeem_claim_secret(db: AsyncSession, secret: str) -> tuple[PortalAccessGrant, str] | None:
    digest = _hash_claim_secret(secret)
    # Serialize redemption attempts on the grant row. Without the lock, two
    # concurrent requests can both observe an unclaimed grant and mint tokens.
    grant = (await db.execute(
        select(PortalAccessGrant)
        .where(PortalAccessGrant.token_hash == digest)
        .with_for_update()
    )).scalar_one_or_none()
    now = datetime.utcnow()
    if not grant or grant.revoked or grant.claimed_at is not None or grant.expires_at <= now:
        return None
    grant.claimed_at = now
    await db.flush()
    return grant, create_guest_portal_token(grant)


async def issue_direct_order_portal_claim(
    db: AsyncSession,
    order: Order,
    *,
    build_name: str,
    contact_email: str,
    manual_build_id: int | None = None,
    created_by: str = "system:dispatch",
    expires_in_days: int = GUEST_PORTAL_TOKEN_DAYS,
) -> tuple[PortalAccessGrant, str]:
    """Issue a one-time, order-scoped claim and save its private print leaflet."""
    if order.id is None or order.customer_id is None:
        raise ValueError("A persisted customer order is required")
    if expires_in_days < 1 or expires_in_days > GUEST_PORTAL_TOKEN_DAYS:
        raise ValueError(f"Claim expiry must be between 1 and {GUEST_PORTAL_TOKEN_DAYS} days")
    locked_order = (await db.execute(
        select(Order).where(Order.id == order.id).with_for_update()
    )).scalar_one_or_none()
    if locked_order is None or locked_order.customer_id != order.customer_id:
        raise ValueError("The verified customer order is no longer available")

    prior_grants = (await db.execute(
        select(PortalAccessGrant)
        .where(
            PortalAccessGrant.order_id == order.id,
            PortalAccessGrant.claimed_at.is_(None),
            PortalAccessGrant.revoked.is_(False),
        )
        .with_for_update()
    )).scalars().all()
    for prior in prior_grants:
        prior.revoked = True

    secret, digest = new_claim_secret()
    grant = PortalAccessGrant(
        order_id=order.id,
        manual_build_id=None,
        contact_email=contact_email.strip().lower(),
        token_hash=digest,
        channel="direct_guest",
        expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
        created_by=created_by,
        email_status="pending",
    )
    db.add(grant)
    await db.flush()
    from app.config import get_settings
    # Keep the one-time bearer secret in the fragment: browsers do not send it
    # to the web server in the HTTP request or include it in normal referrers.
    claim_url = f"{get_settings().frontend_url.rstrip('/')}/claim-build#token={secret}"
    leaflet = create_portal_leaflet(
        build_id=order.id,
        build_name=build_name,
        grant_id=grant.id,
        claim_url=claim_url,
    )
    grant.leaflet_storage_key = leaflet["storage_key"]

    job_query = select(GettingStartedJob).where(GettingStartedJob.order_id == order.id)
    if manual_build_id is not None:
        job_query = select(GettingStartedJob).where(
            or_(GettingStartedJob.order_id == order.id, GettingStartedJob.manual_build_id == manual_build_id)
        )
    job = (await db.execute(job_query)).scalar_one_or_none()
    if job:
        artifacts = [
            item for item in (job.artifact_index or [])
            if not (item.get("category") == "portal_leaflet" and item.get("grant_id") == grant.id)
        ]
        artifacts.append({**leaflet, "category": "portal_leaflet", "private": True})
        job.artifact_index = artifacts
    return grant, claim_url


async def record_portal_claim_email_result(
    db: AsyncSession,
    grant: PortalAccessGrant,
    *,
    sent: bool,
) -> None:
    """Persist the last direct-guest claim email attempt without storing its URL."""
    attempted_at = datetime.utcnow()
    grant.email_status = "sent" if sent else "failed"
    grant.email_attempted_at = attempted_at
    grant.email_sent_at = attempted_at if sent else None
    await db.commit()


async def verify_guest_portal_token(db: AsyncSession, token: str) -> PortalAccessGrant | None:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if claims.get("typ") != "guest_portal" or claims.get("scope") != "portal:read":
        return None
    grant = await db.get(PortalAccessGrant, int(claims.get("grant_id") or 0))
    if not grant or grant.revoked or grant.claimed_at is None:
        return None
    if grant.order_id != claims.get("order_id") or grant.manual_build_id != claims.get("build_id"):
        return None
    return grant


def guest_portal_token_has_capability(token: str, capability: str) -> bool:
    """Check one narrowly-scoped guest portal write capability."""
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return False
    return (
        claims.get("typ") == "guest_portal"
        and claims.get("scope") == "portal:read"
        and capability in (claims.get("capabilities") or [])
    )
