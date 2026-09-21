"""Social post lifecycle for the Growth Engine Marketing MVP."""
from __future__ import annotations

from datetime import datetime, timedelta
import secrets
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.growth import (
    ApprovalRequest,
    AnalyticsEvent,
    ConnectorExecution,
    ContentAsset,
    GrowthAuditEvent,
    PerformanceSnapshot,
    SocialAccount,
    SocialPost,
    SocialPostRevision,
    SocialPublication,
    TrackingLink,
)
from app.services.growth_connectors import (
    PLATFORM_CAPS,
    character_limit,
    organic_snapshot,
    publish_fixture,
)
from app.services.growth_release import FeatureNotEnabled, get_active_release, require_capability

VALID_TRANSITIONS = {
    "draft": {"review", "validation_failed"},
    "validation_failed": {"draft", "review"},
    "review": {"approved", "rejected", "draft"},
    "approved": {"scheduled", "publishing", "draft"},
    "scheduled": {"publishing", "cancelled", "draft"},
    "publishing": {"published", "needs_attention", "timed_out"},
    "published": {"reconciled"},
    "rejected": {"draft"},
    "cancelled": {"draft"},
    "timed_out": {"needs_attention", "cancelled"},
    "needs_attention": {"publishing", "cancelled", "draft"},
    "reconciled": set(),
}

DEFAULT_ACCOUNTS = (
    ("facebook", "FlipFlop Facebook", "@theflipflop"),
    ("instagram", "FlipFlop Instagram", "@theflipflop.shop"),
    ("x", "FlipFlop on X", "@theflipflop"),
)


def _now() -> datetime:
    return datetime.utcnow()


async def audit(db: AsyncSession, action: str, actor: str, subject_type: str, subject_id, detail: dict | None = None):
    db.add(
        GrowthAuditEvent(
            actor=actor,
            action=action,
            subject_type=subject_type,
            subject_id=str(subject_id),
            detail=detail or {},
        )
    )


async def ensure_seed(db: AsyncSession) -> None:
    await get_active_release(db)
    existing = (await db.execute(select(SocialAccount))).scalars().all()
    if not existing:
        for platform, name, handle in DEFAULT_ACCOUNTS:
            db.add(
                SocialAccount(
                    platform=platform,
                    display_name=name,
                    handle=handle,
                    status="connected",
                    capability=PLATFORM_CAPS.get(platform, "fixture"),
                    health="healthy",
                    last_checked_at=_now(),
                )
            )
    assets = (await db.execute(select(ContentAsset))).scalars().all()
    if not assets:
        db.add(
            ContentAsset(
                kind="image",
                title="FlipFlop cube mark",
                url="/pics/flipflop-glow-transparent.png",
                alt_text="FlipFlop glowing cube logo on a dark background",
                approved=True,
                provenance="Owned FlipFlop brand asset",
            )
        )
    await db.flush()


def serialize_account(row: SocialAccount) -> dict:
    return {
        "id": row.id,
        "platform": row.platform,
        "display_name": row.display_name,
        "handle": row.handle,
        "status": row.status,
        "capability": row.capability,
        "health": row.health,
        "health_detail": row.health_detail,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "publish_mode": (
            "Full API publication (fixture/sandbox)"
            if row.capability == "fixture"
            else "Assisted publication"
            if row.capability == "assisted"
            else "Analytics-only"
        ),
    }


def serialize_asset(row: ContentAsset) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "title": row.title,
        "url": row.url,
        "alt_text": row.alt_text,
        "approved": row.approved,
        "provenance": row.provenance,
    }


def serialize_revision(row: SocialPostRevision) -> dict:
    return {
        "id": row.id,
        "post_id": row.post_id,
        "version": row.version,
        "copy": row.copy,
        "platform_variants": row.platform_variants or {},
        "media_asset_ids": row.media_asset_ids or [],
        "link_url": row.link_url,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_post(post: SocialPost, revision: SocialPostRevision | None = None, extras: dict | None = None) -> dict:
    payload = {
        "id": post.id,
        "status": post.status,
        "platforms": post.platforms or [],
        "source_type": post.source_type,
        "source_ref": post.source_ref,
        "author": post.author,
        "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "tracking_link_id": post.tracking_link_id,
        "needs_attention": post.needs_attention,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "revision": serialize_revision(revision) if revision else None,
    }
    if extras:
        payload.update(extras)
    return payload


async def latest_revision(db: AsyncSession, post_id: int) -> SocialPostRevision | None:
    return (
        await db.execute(
            select(SocialPostRevision)
            .where(SocialPostRevision.post_id == post_id)
            .order_by(SocialPostRevision.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def validate_revision(platforms: list[str], revision: SocialPostRevision, assets: list[ContentAsset]) -> list[str]:
    errors: list[str] = []
    if not platforms:
        errors.append("Select at least one destination platform")
    variants = revision.platform_variants or {}
    for platform in platforms:
        copy = (variants.get(platform) or revision.copy or "").strip()
        if not copy:
            errors.append(f"{platform} copy is required")
        elif len(copy) > character_limit(platform):
            errors.append(f"{platform} copy exceeds {character_limit(platform)} characters")
    asset_map = {asset.id: asset for asset in assets}
    for asset_id in revision.media_asset_ids or []:
        asset = asset_map.get(int(asset_id))
        if asset is None:
            errors.append(f"Media asset {asset_id} was not found")
            continue
        if not asset.approved:
            errors.append(f"{asset.title} is not an approved media asset")
        if asset.kind == "image" and not (asset.alt_text or "").strip():
            errors.append(f"{asset.title} needs alternative text")
    return errors


async def _assets_for(db: AsyncSession, ids: list) -> list[ContentAsset]:
    if not ids:
        return []
    rows = (await db.execute(select(ContentAsset).where(ContentAsset.id.in_([int(i) for i in ids])))).scalars().all()
    return list(rows)


async def create_post(db: AsyncSession, payload: dict, actor: str = "owner") -> SocialPost:
    release = await get_active_release(db)
    require_capability(release, "social_publishing")
    await ensure_seed(db)
    post = SocialPost(
        status="draft",
        platforms=payload.get("platforms") or [],
        source_type=payload.get("source_type") or "manual",
        source_ref=payload.get("source_ref") or "",
        author=actor,
        scheduled_for=_parse_dt(payload.get("scheduled_for")),
    )
    db.add(post)
    await db.flush()
    revision = SocialPostRevision(
        post_id=post.id,
        version=1,
        copy=payload.get("copy") or "",
        platform_variants=payload.get("platform_variants") or {},
        media_asset_ids=payload.get("media_asset_ids") or [],
        link_url=payload.get("link_url") or "",
        created_by=actor,
    )
    db.add(revision)
    await db.flush()
    if payload.get("link_url"):
        link = await create_tracking_link(
            db,
            destination_url=payload["link_url"],
            campaign=f"social-post-{post.id}",
            content=str(post.id),
        )
        post.tracking_link_id = link.id
        revision.link_url = tracked_url(link)
    await audit(db, "post.created", actor, "social_post", post.id)
    return post


async def revise_post(db: AsyncSession, post: SocialPost, payload: dict, actor: str = "owner") -> SocialPost:
    current = await latest_revision(db, post.id)
    version = (current.version if current else 0) + 1
    revision = SocialPostRevision(
        post_id=post.id,
        version=version,
        copy=payload.get("copy", current.copy if current else ""),
        platform_variants=payload.get("platform_variants", current.platform_variants if current else {}),
        media_asset_ids=payload.get("media_asset_ids", current.media_asset_ids if current else []),
        link_url=payload.get("link_url", current.link_url if current else ""),
        created_by=actor,
    )
    db.add(revision)
    if payload.get("platforms") is not None:
        post.platforms = payload["platforms"]
    if payload.get("scheduled_for") is not None:
        post.scheduled_for = _parse_dt(payload.get("scheduled_for"))
    if post.status in {"approved", "scheduled", "review"}:
        post.status = "draft"
        await _expire_approvals(db, post.id, "revision_invalidated_approval")
    post.updated_at = _now()
    await audit(db, "post.revised", actor, "social_post", post.id, {"version": version})
    return post


async def submit_for_review(db: AsyncSession, post: SocialPost, actor: str = "owner") -> SocialPost:
    release = await get_active_release(db)
    require_capability(release, "approvals")
    revision = await latest_revision(db, post.id)
    if not revision:
        raise ValueError("Post has no revision")
    assets = await _assets_for(db, revision.media_asset_ids or [])
    errors = validate_revision(post.platforms or [], revision, assets)
    if errors:
        post.status = "validation_failed"
        post.needs_attention = "; ".join(errors)
        await audit(db, "post.validation_failed", actor, "social_post", post.id, {"errors": errors})
        return post
    post.status = "review"
    post.needs_attention = ""
    hours = release.approval_validity_hours or 24
    db.add(
        ApprovalRequest(
            subject_type="social_post",
            subject_id=post.id,
            revision_id=revision.id,
            action="publish",
            status="pending",
            requested_by=actor,
            expires_at=_now() + timedelta(hours=hours),
        )
    )
    await audit(db, "post.submitted", actor, "social_post", post.id, {"revision_id": revision.id})
    return post


async def decide_approval(
    db: AsyncSession,
    post: SocialPost,
    *,
    approve: bool,
    actor: str,
    reason: str = "",
) -> SocialPost:
    release = await get_active_release(db)
    revision = await latest_revision(db, post.id)
    request = await _open_approval(db, post.id)
    if request is None:
        raise ValueError("No pending approval")
    if release.separation_of_duties and actor == request.requested_by:
        raise PermissionError("Author cannot approve their own post while separation of duties is enabled")
    if request.expires_at and request.expires_at < _now():
        request.status = "expired"
        post.status = "draft"
        await audit(db, "approval.expired", actor, "social_post", post.id)
        return post
    request.status = "approved" if approve else "rejected"
    request.decided_by = actor
    request.reason = reason
    request.decided_at = _now()
    post.status = "approved" if approve else "rejected"
    await audit(
        db,
        "post.approved" if approve else "post.rejected",
        actor,
        "social_post",
        post.id,
        {"revision_id": revision.id if revision else None, "reason": reason},
    )
    return post


async def schedule_or_publish(db: AsyncSession, post: SocialPost, actor: str = "owner") -> SocialPost:
    if post.status != "approved":
        raise ValueError("Post must be approved before scheduling or publishing")
    if post.scheduled_for and post.scheduled_for > _now():
        post.status = "scheduled"
        await audit(db, "post.scheduled", actor, "social_post", post.id, {"scheduled_for": post.scheduled_for.isoformat()})
        return post
    return await publish_post(db, post, actor=actor)


async def publish_post(db: AsyncSession, post: SocialPost, actor: str = "system") -> SocialPost:
    release = await get_active_release(db)
    require_capability(release, "social_publishing")
    # A confirmed publication is a successful idempotent retry, not an invalid
    # state transition. Never create another provider action for it.
    if post.status == "published":
        return post
    if post.status not in {"approved", "scheduled", "needs_attention", "publishing"}:
        raise ValueError("Post is not ready to publish")
    revision = await latest_revision(db, post.id)
    if not revision:
        raise ValueError("Post has no revision")
    post.status = "publishing"
    accounts = (
        await db.execute(select(SocialAccount).where(SocialAccount.platform.in_(post.platforms or [])))
    ).scalars().all()
    account_by_platform = {row.platform: row for row in accounts}
    any_failed = False
    any_unknown = False
    for platform in post.platforms or []:
        account = account_by_platform.get(platform)
        if account is None or account.capability == "analytics_only":
            any_failed = True
            continue
        if account.capability == "assisted":
            continue
        key = f"post:{post.id}:rev:{revision.id}:{platform}"
        existing = (
            await db.execute(select(SocialPublication).where(SocialPublication.idempotency_key == key))
        ).scalar_one_or_none()
        if existing and existing.status == "published":
            continue
        if existing and existing.status in {"timed_out", "unknown"}:
            any_unknown = True
            continue
        copy = (revision.platform_variants or {}).get(platform) or revision.copy
        result = publish_fixture(platform=platform, account_id=account.id, copy=copy, idempotency_key=key)
        publication = existing or SocialPublication(
            post_id=post.id,
            revision_id=revision.id,
            account_id=account.id,
            platform=platform,
            idempotency_key=key,
        )
        publication.status = result["status"] if result["status"] != "published" else "published"
        publication.provider_post_id = result["provider_post_id"]
        publication.error = result["error"]
        publication.attempted_at = _now()
        if result["status"] == "published":
            publication.confirmed_at = _now()
            snap = organic_snapshot(result["provider_post_id"], platform)
            db.add(
                PerformanceSnapshot(
                    subject_type="post",
                    subject_id=str(post.id),
                    provider=platform,
                    metrics=snap,
                    retrieved_at=_now(),
                    freshness_seconds=0,
                    source_record=result["provider_post_id"],
                )
            )
        else:
            any_failed = True
        if existing is None:
            db.add(publication)
        db.add(
            ConnectorExecution(
                connector=platform,
                action="publish",
                idempotency_key=key,
                status=publication.status,
                request_payload={"copy": copy, "account_id": account.id},
                response_payload=result,
            )
        )
    if any_unknown:
        post.status = "timed_out"
        post.needs_attention = "Provider result is unknown — reconcile before retrying"
    elif any_failed:
        post.status = "needs_attention"
        post.needs_attention = "One or more platforms failed to publish"
    else:
        post.status = "published"
        post.published_at = _now()
        post.needs_attention = ""
    await audit(db, "post.published", actor, "social_post", post.id, {"status": post.status})
    return post


async def publish_due_posts(db: AsyncSession) -> dict:
    try:
        release = await get_active_release(db)
        require_capability(release, "social_publishing")
    except FeatureNotEnabled:
        return {"published": 0, "skipped": "FEATURE_NOT_ENABLED"}
    due = (
        await db.execute(
            select(SocialPost).where(
                SocialPost.status == "scheduled",
                SocialPost.scheduled_for <= _now(),
            )
        )
    ).scalars().all()
    count = 0
    for post in due:
        await publish_post(db, post, actor="scheduler")
        count += 1
    await db.commit()
    return {"published": count}


async def create_tracking_link(
    db: AsyncSession,
    *,
    destination_url: str,
    campaign: str,
    content: str = "",
    source: str = "social",
    medium: str = "organic",
) -> TrackingLink:
    release = await get_active_release(db)
    require_capability(release, "tracked_links")
    slug = secrets.token_urlsafe(6).replace("_", "").replace("-", "")[:10]
    link = TrackingLink(
        slug=slug,
        destination_url=destination_url,
        utm_source=source,
        utm_medium=medium,
        utm_campaign=campaign,
        utm_content=content,
    )
    db.add(link)
    await db.flush()
    return link


def tracked_url(link: TrackingLink) -> str:
    parsed = urlparse(link.destination_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "utm_source": link.utm_source,
            "utm_medium": link.utm_medium,
            "utm_campaign": link.utm_campaign,
            "utm_content": link.utm_content or link.slug,
        }
    )
    return urlunparse(parsed._replace(query=urlencode(query)))


async def ingest_website_event(db: AsyncSession, payload: dict) -> AnalyticsEvent:
    release = await get_active_release(db)
    require_capability(release, "website_analytics")
    event = AnalyticsEvent(
        source=payload.get("source") or "website",
        event_name=payload.get("event_name") or "page_view",
        session_id=payload.get("session_id") or "",
        path=payload.get("path") or "",
        utm=payload.get("utm") or {},
        properties=payload.get("properties") or {},
        occurred_at=_parse_dt(payload.get("occurred_at")) or _now(),
    )
    db.add(event)
    await db.flush()
    return event


async def analytics_summary(db: AsyncSession) -> dict:
    events = (await db.execute(select(AnalyticsEvent))).scalars().all()
    snapshots = (await db.execute(select(PerformanceSnapshot))).scalars().all()
    sessions = len({event.session_id for event in events if event.session_id})
    latest = max((row.retrieved_at for row in snapshots), default=None)
    return {
        "website_events": len(events),
        "website_sessions": sessions,
        "utm_visits": sum(1 for event in events if event.utm),
        "post_snapshots": len(snapshots),
        "freshness": latest.isoformat() if latest else None,
        "source": "internal_ingestion",
        "label": "Organic metrics and website sessions only",
    }


async def command_centre(db: AsyncSession) -> dict:
    await ensure_seed(db)
    posts = (await db.execute(select(SocialPost))).scalars().all()
    approvals = (
        await db.execute(select(ApprovalRequest).where(ApprovalRequest.status == "pending"))
    ).scalars().all()
    accounts = (await db.execute(select(SocialAccount))).scalars().all()
    summary = await analytics_summary(db)
    today = _now().date()
    return {
        "approvals_pending": len(approvals),
        "drafts": sum(1 for post in posts if post.status == "draft"),
        "scheduled_today": sum(
            1
            for post in posts
            if post.status == "scheduled" and post.scheduled_for and post.scheduled_for.date() == today
        ),
        "needs_attention": sum(1 for post in posts if post.status in {"needs_attention", "timed_out", "validation_failed"}),
        "published": sum(1 for post in posts if post.status == "published"),
        "account_health": [
            {"platform": row.platform, "health": row.health, "status": row.status, "capability": row.capability}
            for row in accounts
        ],
        "analytics": summary,
        "roadmap_hidden_claims": [
            "Revenue attributed to growth activity is not shown in Marketing MVP",
            "Advertising spend is a later-phase capability",
        ],
    }


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


async def _open_approval(db: AsyncSession, post_id: int) -> ApprovalRequest | None:
    return (
        await db.execute(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.subject_type == "social_post",
                ApprovalRequest.subject_id == post_id,
                ApprovalRequest.status == "pending",
            )
            .order_by(ApprovalRequest.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _expire_approvals(db: AsyncSession, post_id: int, reason: str) -> None:
    rows = (
        await db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.subject_type == "social_post",
                ApprovalRequest.subject_id == post_id,
                ApprovalRequest.status == "pending",
            )
        )
    ).scalars().all()
    for row in rows:
        row.status = "revoked"
        row.reason = reason
        row.decided_at = _now()
