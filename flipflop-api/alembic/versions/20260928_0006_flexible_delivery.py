"""Add the curated/custom Flexible delivery window."""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260928_06"
down_revision = "vnext_20260928_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("flexible_curated_custom_days", sa.Integer(), nullable=False, server_default="10"))


def downgrade() -> None:
    op.drop_column("app_settings", "flexible_curated_custom_days")
