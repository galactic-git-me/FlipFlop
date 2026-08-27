"""Add owner-controlled batches for 3D asset review.

Revision ID: 20260827_0017
Revises: 20260826_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827_0017"
down_revision = "20260826_0016"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    op.add_column("component_3d_assets", sa.Column("review_batch_id", sa.String(36), nullable=True))
    op.add_column("component_3d_assets", sa.Column("review_decision", sa.String(20), nullable=True))
    op.add_column("component_3d_assets", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("component_3d_assets", sa.Column("reviewed_by", sa.String(100), nullable=True))
    op.create_index("ix_component_3d_assets_review_batch_id", "component_3d_assets", ["review_batch_id"])
    if not sa.inspect(op.get_bind()).has_table("cases"):
        # The original cases catalogue predates Alembic in some deployments,
        # but a clean PostgreSQL deployment has no table-creation revision.
        op.create_table(
            "cases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("brand", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("source_site", sa.String(), nullable=False),
            sa.Column("source_url", sa.String(), nullable=True),
            sa.Column("image_url", sa.String(), nullable=True),
            sa.Column("price", sa.Float(), nullable=True),
            sa.Column("price_new", sa.Float(), nullable=True),
            sa.Column("rrp", sa.Float(), nullable=True),
            sa.Column("rating", sa.Float(), nullable=True),
            sa.Column("review_count", sa.Integer(), nullable=True),
            sa.Column("sales_velocity", sa.String(), nullable=True),
            sa.Column("bestseller_rank", sa.Integer(), nullable=True),
            sa.Column("form_factors", sa.JSON(), nullable=True),
            sa.Column("keywords", sa.JSON(), nullable=True),
            sa.Column("has_3d_model", sa.Boolean(), nullable=True),
            sa.Column("model_3d_url", sa.String(), nullable=True),
            sa.Column("model_3d_source", sa.String(), nullable=True),
            sa.Column("model_3d_creator", sa.String(), nullable=True),
            sa.Column("model_3d_license", sa.String(), nullable=True),
            sa.Column("model_3d_quality", sa.String(), nullable=True),
            sa.Column("model_3d_vertices", sa.Integer(), nullable=True),
            sa.Column("model_3d_polygons", sa.Integer(), nullable=True),
            sa.Column("model_3d_file_size", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("priority_3d_rank", sa.Integer(), nullable=True),
            sa.Column("priority_3d_batch", sa.Integer(), nullable=True),
            sa.Column("priority_3d_frozen_at", sa.DateTime(), nullable=True),
            sa.Column("sourcing_3d_evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    else:
        case_columns = _column_names("cases")
        for column in (
            sa.Column("priority_3d_rank", sa.Integer(), nullable=True),
            sa.Column("priority_3d_batch", sa.Integer(), nullable=True),
            sa.Column("priority_3d_frozen_at", sa.DateTime(), nullable=True),
            sa.Column("sourcing_3d_evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        ):
            if column.name not in case_columns:
                op.add_column("cases", column)

    case_indexes = _index_names("cases")
    if "ix_cases_priority_3d_rank" not in case_indexes:
        op.create_index("ix_cases_priority_3d_rank", "cases", ["priority_3d_rank"])
    if "ix_cases_priority_3d_batch" not in case_indexes:
        op.create_index("ix_cases_priority_3d_batch", "cases", ["priority_3d_batch"])


def downgrade() -> None:
    op.drop_index("ix_cases_priority_3d_batch", table_name="cases")
    op.drop_index("ix_cases_priority_3d_rank", table_name="cases")
    op.drop_column("cases", "sourcing_3d_evidence")
    op.drop_column("cases", "priority_3d_frozen_at")
    op.drop_column("cases", "priority_3d_batch")
    op.drop_column("cases", "priority_3d_rank")
    op.drop_index("ix_component_3d_assets_review_batch_id", table_name="component_3d_assets")
    op.drop_column("component_3d_assets", "reviewed_by")
    op.drop_column("component_3d_assets", "reviewed_at")
    op.drop_column("component_3d_assets", "review_decision")
    op.drop_column("component_3d_assets", "review_batch_id")
