"""Add per-build FAQ answer overrides."""

from alembic import op
import sqlalchemy as sa

revision = "20260819_0003"
down_revision = "20260819_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_builds",
        sa.Column("selected_faq_answer_overrides", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )


def downgrade() -> None:
    op.drop_column("manual_builds", "selected_faq_answer_overrides")
