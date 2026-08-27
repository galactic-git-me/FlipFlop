"""Add CPK identity, ownership, lifecycle and evidence to component alerts."""

from alembic import op
import sqlalchemy as sa

revision = "20260827_0020"
down_revision = "20260827_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_alerts", sa.Column("owner_admin_id", sa.Integer(), nullable=True))
    op.add_column("price_alerts", sa.Column("cpk", sa.String(length=64), nullable=True))
    op.add_column("price_alerts", sa.Column("condition_cohort", sa.String(length=20), nullable=True))
    op.add_column("price_alerts", sa.Column("monitoring_status", sa.String(length=30), nullable=False, server_default="armed"))
    op.add_column("price_alerts", sa.Column("reference_evidence_json", sa.JSON(), nullable=True))
    op.add_column("price_alerts", sa.Column("triggered_evidence_json", sa.JSON(), nullable=True))
    op.add_column("price_alerts", sa.Column("last_evaluated_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_price_alert_owner_admin", "price_alerts", "admin_users", ["owner_admin_id"], ["id"])
    op.create_index("ix_price_alerts_owner_admin_id", "price_alerts", ["owner_admin_id"])
    op.create_index("ix_price_alerts_cpk", "price_alerts", ["cpk"])
    op.create_index("ix_price_alerts_monitoring_status", "price_alerts", ["monitoring_status"])
    op.alter_column("price_alerts", "target_price_gbp", existing_type=sa.Integer(), nullable=True)
    op.execute("""
        UPDATE price_alerts p SET owner_admin_id = a.id
        FROM admin_users a WHERE LOWER(a.email) = LOWER(p.user_email)
    """)
    op.execute("UPDATE price_alerts SET monitoring_status='triggered' WHERE triggered_at IS NOT NULL")
    op.execute("UPDATE price_alerts SET monitoring_status='dismissed' WHERE is_active IS FALSE")
    op.execute("""
        UPDATE price_alerts SET monitoring_status='pending_identity', target_price_gbp=NULL,
          triggered_at=NULL, triggered_price_gbp=NULL, triggered_listing_url=NULL,
          reference_basis=NULL
        WHERE alert_type='component'
    """)
    op.execute("""
        UPDATE price_alerts SET cpk='77c01c76a88606a1', condition_cohort='used',
          monitoring_status='triggered', target_price_gbp=14110,
          triggered_at='2026-08-26 17:39:47.998878', triggered_price_gbp=12999,
          triggered_listing_url='https://www.ebay.co.uk/itm/157576930746',
          reference_basis='market_median'
        WHERE component_key='ASUS PRIME X870-P'
    """)
    op.execute("""
        UPDATE price_alerts SET cpk='205ebca72cf63e4c', condition_cohort='new',
          monitoring_status='armed', target_price_gbp=4249,
          triggered_listing_url='https://www.overclockers.co.uk/apnx-creator-c1-chromaflair-mid-tower-case-cas-aer-00612.html',
          reference_basis='fixed_retailer'
        WHERE component_key='APNX ChromaFlair Iridescent Chassis'
    """)
    op.drop_index("uq_price_alerts_component_key", table_name="price_alerts")
    op.execute("CREATE UNIQUE INDEX uq_price_alert_owner_cpk ON price_alerts (owner_admin_id, cpk) WHERE alert_type='component' AND cpk IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_price_alert_owner_cpk")
    op.execute("CREATE UNIQUE INDEX uq_price_alerts_component_key ON price_alerts (component_key) WHERE alert_type='component'")
    op.alter_column("price_alerts", "target_price_gbp", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_price_alerts_monitoring_status", table_name="price_alerts")
    op.drop_index("ix_price_alerts_cpk", table_name="price_alerts")
    op.drop_index("ix_price_alerts_owner_admin_id", table_name="price_alerts")
    op.drop_constraint("fk_price_alert_owner_admin", "price_alerts", type_="foreignkey")
    for name in ("last_evaluated_at", "triggered_evidence_json", "reference_evidence_json", "monitoring_status", "condition_cohort", "cpk", "owner_admin_id"):
        op.drop_column("price_alerts", name)
