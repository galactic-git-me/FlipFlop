"""Growth Engine persistence — Marketing MVP plus shared governance tables.

Later-phase entities (paid ads, newsletters, offers) are intentionally omitted
until their phase PRDs are enabled in `growth_release_configuration`.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


MVP_CAPABILITIES = (
    "social_publishing",
    "content_calendar",
    "website_analytics",
    "tracked_links",
    "approvals",
    "audit",
)

ROADMAP_CAPABILITIES = (
    "paid_advertising",
    "blog_publishing",
    "newsletters",
    "automated_replies",
    "vouchers",
    "loyalty",
    "abandoned_cart",
    "revenue_attribution",
    "controlled_optimisation",
)


class GrowthReleaseConfiguration(Base):
    __tablename__ = "growth_release_configuration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_name: Mapped[str] = mapped_column(String(80), default="marketing_mvp")
    version: Mapped[str] = mapped_column(String(20), default="1.2")
    enabled_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    enabled_channels: Mapped[list] = mapped_column(JSON, default=list)
    enabled_agents: Mapped[list] = mapped_column(JSON, default=list)
    approval_policy_version: Mapped[str] = mapped_column(String(20), default="1.0")
    financial_policy_version: Mapped[str] = mapped_column(String(20), default="1.0")
    consent_policy_version: Mapped[str] = mapped_column(String(20), default="1.0")
    single_user_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    separation_of_duties: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_validity_hours: Mapped[int] = mapped_column(Integer, default=24)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_by: Mapped[str] = mapped_column(String(120), default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SocialAccount(Base):
    __tablename__ = "growth_social_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    handle: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="connected")  # connected, expired, revoked, error
    capability: Mapped[str] = mapped_column(String(40), default="fixture")  # fixture, assisted, analytics_only
    health: Mapped[str] = mapped_column(String(40), default="healthy")
    health_detail: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContentAsset(Base):
    __tablename__ = "growth_content_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), default="image")  # image, video, copy
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(2000), default="")
    alt_text: Mapped[str] = mapped_column(String(500), default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    provenance: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SocialPost(Base):
    __tablename__ = "growth_social_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    platforms: Mapped[list] = mapped_column(JSON, default=list)
    source_type: Mapped[str] = mapped_column(String(40), default="manual")
    source_ref: Mapped[str] = mapped_column(String(200), default="")
    author: Mapped[str] = mapped_column(String(120), default="owner")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    tracking_link_id: Mapped[int | None] = mapped_column(Integer)
    needs_attention: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SocialPostRevision(Base):
    __tablename__ = "growth_social_post_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    copy: Mapped[str] = mapped_column(Text, default="")
    platform_variants: Mapped[dict] = mapped_column(JSON, default=dict)
    media_asset_ids: Mapped[list] = mapped_column(JSON, default=list)
    link_url: Mapped[str] = mapped_column(String(2000), default="")
    created_by: Mapped[str] = mapped_column(String(120), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SocialPublication(Base):
    __tablename__ = "growth_social_publications"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_growth_publication_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, index=True)
    revision_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    provider_post_id: Mapped[str] = mapped_column(String(200), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(120))
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrackingLink(Base):
    __tablename__ = "growth_tracking_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    destination_url: Mapped[str] = mapped_column(String(2000))
    utm_source: Mapped[str] = mapped_column(String(80), default="social")
    utm_medium: Mapped[str] = mapped_column(String(80), default="organic")
    utm_campaign: Mapped[str] = mapped_column(String(120), default="")
    utm_content: Mapped[str] = mapped_column(String(120), default="")
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnalyticsEvent(Base):
    __tablename__ = "growth_analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)  # website, social
    event_name: Mapped[str] = mapped_column(String(80), index=True)
    session_id: Mapped[str] = mapped_column(String(120), default="")
    path: Mapped[str] = mapped_column(String(500), default="")
    utm: Mapped[dict] = mapped_column(JSON, default=dict)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PerformanceSnapshot(Base):
    __tablename__ = "growth_performance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(40), index=True)  # post, website
    subject_id: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(80), default="internal")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    freshness_seconds: Mapped[int] = mapped_column(Integer, default=0)
    source_record: Mapped[str] = mapped_column(String(200), default="")


class ApprovalRequest(Base):
    __tablename__ = "growth_approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(40), index=True)
    subject_id: Mapped[int] = mapped_column(Integer, index=True)
    revision_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(80), default="publish")
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    requested_by: Mapped[str] = mapped_column(String(120), default="owner")
    decided_by: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConnectorExecution(Base):
    __tablename__ = "growth_connector_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default="succeeded")
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GrowthAuditEvent(Base):
    __tablename__ = "growth_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), default="owner")
    action: Mapped[str] = mapped_column(String(120), index=True)
    subject_type: Mapped[str] = mapped_column(String(40), default="")
    subject_id: Mapped[str] = mapped_column(String(80), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
