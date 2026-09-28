"""Add per-playbook-cell permission for recovered flip components."""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260928_05"
down_revision = "vnext_20260928_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "curated_build_segments",
        sa.Column("allow_flip_component_sources", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("curated_build_segments", "allow_flip_component_sources")
