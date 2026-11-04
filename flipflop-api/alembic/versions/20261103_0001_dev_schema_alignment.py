"""Align DEV server defaults and safe nullability with production."""

import re

from alembic import op
import sqlalchemy as sa

revision = "20261103_0001"
down_revision = "20261101_0001"
branch_labels = None
depends_on = None

PRODUCTION_DEFAULTS = [
    ('ai_setup_purchases', 'status', "'pending'::character varying"),
    ('app_settings', 'flexible_curated_custom_days', '10'),
    ('catalogue_marketing_copy', 'context_key', "'product'::character varying"),
    ('catalogue_marketing_copy', 'generated_at', 'now()'),
    ('catalogue_marketing_copy', 'updated_at', 'now()'),
    ('component_manuals', 'is_active', 'true'),
    ('curated_build_segments', 'availability_status', "'in_stock'::character varying"),
    ('curated_build_segments', 'is_live', 'false'),
    ('curated_build_segments', 'regeneration_status', "'idle'::character varying"),
    ('curated_build_segments', 'allow_flip_component_sources', 'false'),
    ('custom_build_settings', 'id', "nextval('custom_build_settings_id_seq'::regclass)"),
    ('custom_build_settings', 'is_live', 'false'),
    ('customer_problem_notifications', 'attempt_count', '0'),
    ('customer_problem_notifications', 'state', "'pending'::character varying"),
    ('customer_problem_notifications', 'created_at', 'now()'),
    ('getting_started_jobs', 'source_type', "'ready_to_ship'::character varying"),
    ('getting_started_jobs', 'status', "'awaiting_review'::character varying"),
    ('growth_analytics_events', 'session_id', "''::character varying"),
    ('growth_analytics_events', 'path', "''::character varying"),
    ('growth_approval_requests', 'action', "'publish'::character varying"),
    ('growth_approval_requests', 'status', "'pending'::character varying"),
    ('growth_approval_requests', 'requested_by', "'owner'::character varying"),
    ('growth_approval_requests', 'reason', "''::text"),
    ('growth_audit_events', 'actor', "'owner'::character varying"),
    ('growth_audit_events', 'subject_type', "''::character varying"),
    ('growth_audit_events', 'subject_id', "''::character varying"),
    ('growth_connector_executions', 'status', "'succeeded'::character varying"),
    ('growth_content_assets', 'kind', "'image'::character varying"),
    ('growth_content_assets', 'url', "''::character varying"),
    ('growth_content_assets', 'alt_text', "''::character varying"),
    ('growth_content_assets', 'approved', 'false'),
    ('growth_content_assets', 'provenance', "''::text"),
    ('growth_performance_snapshots', 'provider', "'internal'::character varying"),
    ('growth_performance_snapshots', 'freshness_seconds', '0'),
    ('growth_performance_snapshots', 'source_record', "''::character varying"),
    ('growth_release_configuration', 'release_name', "'marketing_mvp'::character varying"),
    ('growth_release_configuration', 'version', "'1.2'::character varying"),
    ('growth_release_configuration', 'approval_policy_version', "'1.0'::character varying"),
    ('growth_release_configuration', 'financial_policy_version', "'1.0'::character varying"),
    ('growth_release_configuration', 'consent_policy_version', "'1.0'::character varying"),
    ('growth_release_configuration', 'single_user_mode', 'true'),
    ('growth_release_configuration', 'separation_of_duties', 'false'),
    ('growth_release_configuration', 'approval_validity_hours', '24'),
    ('growth_release_configuration', 'approved_by', "'owner'::character varying"),
    ('growth_release_configuration', 'is_active', 'true'),
    ('growth_social_accounts', 'handle', "''::character varying"),
    ('growth_social_accounts', 'status', "'connected'::character varying"),
    ('growth_social_accounts', 'capability', "'fixture'::character varying"),
    ('growth_social_accounts', 'health', "'healthy'::character varying"),
    ('growth_social_accounts', 'health_detail', "''::text"),
    ('growth_social_post_revisions', 'version', '1'),
    ('growth_social_post_revisions', 'copy', "''::text"),
    ('growth_social_post_revisions', 'link_url', "''::character varying"),
    ('growth_social_post_revisions', 'created_by', "'owner'::character varying"),
    ('growth_social_posts', 'status', "'draft'::character varying"),
    ('growth_social_posts', 'source_type', "'manual'::character varying"),
    ('growth_social_posts', 'source_ref', "''::character varying"),
    ('growth_social_posts', 'author', "'owner'::character varying"),
    ('growth_social_posts', 'needs_attention', "''::text"),
    ('growth_social_publications', 'status', "'queued'::character varying"),
    ('growth_social_publications', 'provider_post_id', "''::character varying"),
    ('growth_social_publications', 'error', "''::text"),
    ('growth_tracking_links', 'utm_source', "'social'::character varying"),
    ('growth_tracking_links', 'utm_medium', "'organic'::character varying"),
    ('growth_tracking_links', 'utm_campaign', "''::character varying"),
    ('growth_tracking_links', 'utm_content', "''::character varying"),
    ('growth_tracking_links', 'click_count', '0'),
    ('manual_builds', 'warranty_reserve_pct', "'5'::double precision"),
    ('manual_builds', 'shipping_insurance_status', "'not_created'::character varying"),
    ('manual_builds', 'shipment_booking_state', "'not_started'::character varying"),
    ('newsletter_subscriptions', 'status', "'pending'::character varying"),
    ('newsletter_subscriptions', 'consent_version', "'footer-v1'::character varying"),
    ('newsletter_subscriptions', 'created_at', 'now()'),
    ('order_payment_observations', 'amount_refunded_minor', '0'),
    ('portal_access_grants', 'channel', "'direct_guest'::character varying"),
    ('portal_access_grants', 'revoked', 'false'),
    ('shipment_tracking_events', 'material', 'false'),
    ('shipment_tracking_events', 'customer_notification_attempts', '0'),
    ('supplier_offer_evidence', 'delivery_estimate_source', "'vendor_default'::character varying"),
    ('warranty_claims', 'status', "'open'::character varying"),
    ('warranty_claims', 'approved_cost_gbp', "'0'::double precision"),
    ('warranty_reserves', 'allocated_claim_amount_gbp', "'0'::double precision"),
    ('warranty_reserves', 'released_amount_gbp', "'0'::double precision"),
    ('warranty_reserves', 'status', "'held'::character varying"),
]

PRODUCTION_NULLABLE = [
    ('customer_problems', 'order_id'),
    ('customer_problems', 'customer_id'),
    ('growth_analytics_events', 'utm'),
    ('growth_analytics_events', 'properties'),
    ('growth_analytics_events', 'occurred_at'),
    ('growth_analytics_events', 'ingested_at'),
    ('growth_approval_requests', 'created_at'),
    ('growth_audit_events', 'detail'),
    ('growth_audit_events', 'created_at'),
    ('growth_connector_executions', 'request_payload'),
    ('growth_connector_executions', 'response_payload'),
    ('growth_connector_executions', 'created_at'),
    ('growth_content_assets', 'created_at'),
    ('growth_performance_snapshots', 'metrics'),
    ('growth_performance_snapshots', 'retrieved_at'),
    ('growth_release_configuration', 'enabled_capabilities'),
    ('growth_release_configuration', 'enabled_channels'),
    ('growth_release_configuration', 'enabled_agents'),
    ('growth_release_configuration', 'effective_at'),
    ('growth_release_configuration', 'created_at'),
    ('growth_social_accounts', 'created_at'),
    ('growth_social_post_revisions', 'platform_variants'),
    ('growth_social_post_revisions', 'media_asset_ids'),
    ('growth_social_post_revisions', 'created_at'),
    ('growth_social_posts', 'platforms'),
    ('growth_social_posts', 'created_at'),
    ('growth_social_posts', 'updated_at'),
    ('growth_social_publications', 'created_at'),
    ('growth_tracking_links', 'created_at'),
]

PRODUCTION_NOT_NULL = [
    ('app_settings', 'storefront_trust_messages'),
    ('app_settings', 'storefront_trust_message_seconds'),
]

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names(schema="public"))
    for table, column, expected in PRODUCTION_DEFAULTS:
        if table not in tables:
            continue
        current = next((item for item in inspector.get_columns(table, schema="public") if item["name"] == column), None)
        if current is not None and current.get("default") != expected:
            sequence_match = re.fullmatch(r"nextval\('([a-zA-Z0-9_]+)'::regclass\)", expected)
            if sequence_match:
                sequence = sequence_match.group(1)
                exists = bind.execute(
                    sa.text("SELECT to_regclass(:name)"),
                    {"name": f"public.{sequence}"},
                ).scalar_one()
                if exists is None:
                    op.execute(sa.schema.CreateSequence(sa.Sequence(sequence, schema="public")))
                    op.execute(
                        sa.text(
                            f'ALTER SEQUENCE public."{sequence}" '
                            f'OWNED BY public."{table}"."{column}"'
                        )
                    )
                    maximum = bind.execute(
                        sa.text(f'SELECT COALESCE(MAX("{column}"), 0) FROM public."{table}"')
                    ).scalar_one()
                    bind.execute(
                        sa.text("SELECT setval(CAST(:name AS regclass), :value, :called)"),
                        {
                            "name": f"public.{sequence}",
                            "value": maximum if maximum else 1,
                            "called": bool(maximum),
                        },
                    )
            op.alter_column(table, column, schema="public", server_default=sa.text(expected))
            inspector = sa.inspect(bind)
    for table, column in PRODUCTION_NULLABLE:
        if table not in tables:
            continue
        current = next((item for item in inspector.get_columns(table, schema="public") if item["name"] == column), None)
        if current is not None and not current.get("nullable", True):
            op.alter_column(table, column, schema="public", nullable=True)
            inspector = sa.inspect(bind)
    for table, column in PRODUCTION_NOT_NULL:
        if table not in tables:
            continue
        current = next((item for item in inspector.get_columns(table, schema="public") if item["name"] == column), None)
        if current is None or not current.get("nullable", False):
            continue
        count = bind.execute(sa.text(f'SELECT count(*) FROM public."{table}" WHERE "{column}" IS NULL')).scalar_one()
        if count:
            raise RuntimeError(f"Cannot align {table}.{column}: {count} NULL row(s) require an explicit data decision")
        op.alter_column(table, column, schema="public", nullable=False)
        inspector = sa.inspect(bind)

def downgrade():
    raise RuntimeError("Schema alignment is forward-only; restore a verified DEV schema backup to roll back")
