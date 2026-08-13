"""Bridge PCBuild into Build orchestration record via PREBUILT build type.

Adds:
- BuildType.PREBUILT to support admin PC Builder workflows
- builds.pcbuild_id FK to associate orchestration records with PCBuild designs
- pc_builds.stage to track design→build→sell workflow (replaces flat status field)

Revision ID: 20260723_0019
Revises: 20260717_0018
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0019"
down_revision = "20260717_0018"
depends_on = None


def upgrade():
    # Add pcbuild_id FK to builds table
    op.add_column("builds", sa.Column("pcbuild_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_builds_pcbuild_id", "builds", "pc_builds", ["pcbuild_id"], ["id"])

    # Add stage column to pc_builds with default "design"
    op.add_column(
        "pc_builds",
        sa.Column("stage", sa.String(20), nullable=False, server_default="design"),
    )
    op.create_index("ix_pc_builds_stage", "pc_builds", ["stage"])

    # Alter builds.build_type enum to include PREBUILT
    # SQLite doesn't support ALTER TYPE directly, so we need to use a raw SQL approach
    # For PostgreSQL this would be: ALTER TYPE build_type ADD VALUE 'prebuilt';
    # For SQLite we're limited — the Enum is just a string constraint, so no change needed at DB level
    # The Python enum change is sufficient


def downgrade():
    op.drop_index("ix_pc_builds_stage", table_name="pc_builds")
    op.drop_column("pc_builds", "stage")
    op.drop_constraint("fk_builds_pcbuild_id", "builds", type_="foreignkey")
    op.drop_column("builds", "pcbuild_id")
