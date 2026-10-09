"""Growth Engine Marketing MVP tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260921_0001"
down_revision = "20260919_0001"
depends_on = None


def upgrade():
    op.create_table(
        "growth_release_configuration",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("release_name", sa.String(80), nullable=False, server_default="marketing_mvp"),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.2"),
        sa.Column("enabled_capabilities", sa.JSON(), nullable=True),
        sa.Column("enabled_channels", sa.JSON(), nullable=True),
        sa.Column("enabled_agents", sa.JSON(), nullable=True),
        sa.Column("approval_policy_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("financial_policy_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("consent_policy_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("single_user_mode", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("separation_of_duties", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval_validity_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("effective_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", sa.String(120), nullable=False, server_default="owner"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_social_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("handle", sa.String(120), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="connected"),
        sa.Column("capability", sa.String(40), nullable=False, server_default="fixture"),
        sa.Column("health", sa.String(40), nullable=False, server_default="healthy"),
        sa.Column("health_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_content_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False, server_default="image"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False, server_default=""),
        sa.Column("alt_text", sa.String(500), nullable=False, server_default=""),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_social_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("platforms", sa.JSON(), nullable=True),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(200), nullable=False, server_default=""),
        sa.Column("author", sa.String(120), nullable=False, server_default="owner"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("tracking_link_id", sa.Integer(), nullable=True),
        sa.Column("needs_attention", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_social_post_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("copy", sa.Text(), nullable=False, server_default=""),
        sa.Column("platform_variants", sa.JSON(), nullable=True),
        sa.Column("media_asset_ids", sa.JSON(), nullable=True),
        sa.Column("link_url", sa.String(2000), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(120), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_social_publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("provider_post_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_growth_publication_idempotency"),
    )
    op.create_table(
        "growth_tracking_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("destination_url", sa.String(2000), nullable=False),
        sa.Column("utm_source", sa.String(80), nullable=False, server_default="social"),
        sa.Column("utm_medium", sa.String(80), nullable=False, server_default="organic"),
        sa.Column("utm_campaign", sa.String(120), nullable=False, server_default=""),
        sa.Column("utm_content", sa.String(120), nullable=False, server_default=""),
        sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "growth_analytics_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("event_name", sa.String(80), nullable=False),
        sa.Column("session_id", sa.String(120), nullable=False, server_default=""),
        sa.Column("path", sa.String(500), nullable=False, server_default=""),
        sa.Column("utm", sa.JSON(), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_performance_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False, server_default="internal"),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(), nullable=True),
        sa.Column("freshness_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_record", sa.String(200), nullable=False, server_default=""),
    )
    op.create_table(
        "growth_approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(80), nullable=False, server_default="publish"),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(120), nullable=False, server_default="owner"),
        sa.Column("decided_by", sa.String(120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_connector_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connector", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="succeeded"),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "growth_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(120), nullable=False, server_default="owner"),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("subject_type", sa.String(40), nullable=False, server_default=""),
        sa.Column("subject_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    for table in (
        "growth_audit_events",
        "growth_connector_executions",
        "growth_approval_requests",
        "growth_performance_snapshots",
        "growth_analytics_events",
        "growth_tracking_links",
        "growth_social_publications",
        "growth_social_post_revisions",
        "growth_social_posts",
        "growth_content_assets",
        "growth_social_accounts",
        "growth_release_configuration",
    ):
        op.drop_table(table)
