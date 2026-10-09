"""Persist supplier offer evidence and immutable pricing snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260928_01"
down_revision = "vnext_20260926_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_offer_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_key", sa.String(length=160), nullable=False),
        sa.Column("supplier", sa.String(length=160), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("condition", sa.String(length=20), nullable=False),
        sa.Column("item_gbp", sa.Numeric(12, 2), nullable=False),
        sa.Column("delivery_gbp", sa.Numeric(12, 2), nullable=False),
        sa.Column("fees_gbp", sa.Numeric(12, 2), nullable=False),
        sa.Column("risk_gbp", sa.Numeric(12, 2), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stock_confirmed", sa.Boolean(), nullable=False),
        sa.Column("delivery_working_days", sa.Integer(), nullable=True),
        sa.Column("supplier_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("evidence_source", sa.String(length=160), nullable=False),
        sa.Column("evidence_ref", sa.String(length=500), nullable=False),
        sa.Column("captured_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_supplier_offer_evidence_part_key", "supplier_offer_evidence", ["part_key"])
    op.create_table(
        "price_quote_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_price_quote_snapshots_product_key", "price_quote_snapshots", ["product_key"])


def downgrade() -> None:
    op.drop_index("ix_price_quote_snapshots_product_key", table_name="price_quote_snapshots")
    op.drop_table("price_quote_snapshots")
    op.drop_index("ix_supplier_offer_evidence_part_key", table_name="supplier_offer_evidence")
    op.drop_table("supplier_offer_evidence")
