"""Add the Growth Engine global dispatch pause control."""

from alembic import op
import sqlalchemy as sa


revision = "20261126_0001_growth_dispatch_control"
down_revision = "20261122_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "growth_dispatch_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(120), nullable=False, server_default="system"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        "INSERT INTO growth_dispatch_control (id, is_paused, reason, updated_by) "
        "VALUES (1, TRUE, 'Publishing remains paused until a live provider is verified', 'system')"
    )


def downgrade() -> None:
    op.drop_table("growth_dispatch_control")
