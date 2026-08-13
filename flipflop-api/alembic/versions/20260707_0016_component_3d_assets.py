"""Component 3D asset registry for the modular configurator

Versioned per-subject asset rows carrying the Meshy lifecycle
(MISSING → MESHY_DRAFT → CLEANED → VALIDATED → FINAL / REJECTED),
GLB refs, scale validation and case anchor manifests. Distinct from
capture_3d_assets, which remains the per-order completed-build twin.
See FlipFlop.shop/ANALYSIS_AND_IMPLEMENTATION_PLAN.md Sections D–E.

Revision ID: 20260707_0016
Revises: 20260706_0015
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = "20260707_0016"
down_revision = "20260706_0015"
depends_on = None


def upgrade():
    op.create_table(
        "component_3d_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "subject_type",
            sa.Enum("CASE", "VARIANT", "CATEGORY_GENERIC", name="assetsubjecttype"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "MISSING", "MESHY_DRAFT", "CLEANED", "VALIDATED", "FINAL", "REJECTED",
                name="component3dassetstatus",
            ),
            nullable=False,
            server_default="MISSING",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("glb_ref", sa.String(length=1000), nullable=True),
        sa.Column("preview_image_ref", sa.String(length=1000), nullable=True),
        sa.Column("source_image_refs", sa.JSON(), nullable=True),
        sa.Column("poly_count", sa.Integer(), nullable=True),
        sa.Column("file_size_kb", sa.Integer(), nullable=True),
        sa.Column("dimensions_mm", sa.JSON(), nullable=True),
        sa.Column("scale_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("anchor_manifest_json", sa.JSON(), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_c3da_subject", "component_3d_assets", ["subject_type", "subject_id"])
    op.create_index(
        "ix_c3da_active", "component_3d_assets", ["subject_type", "subject_id", "is_active"]
    )


def downgrade():
    op.drop_index("ix_c3da_active", table_name="component_3d_assets")
    op.drop_index("ix_c3da_subject", table_name="component_3d_assets")
    op.drop_table("component_3d_assets")
    sa.Enum(name="component3dassetstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="assetsubjecttype").drop(op.get_bind(), checkfirst=True)
