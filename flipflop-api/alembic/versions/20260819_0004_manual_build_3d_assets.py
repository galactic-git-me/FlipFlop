"""Store per-build image-to-3D generation jobs and assets."""
from alembic import op
import sqlalchemy as sa

revision = "20260819_0004"
down_revision = "20260819_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "manual_builds",
        sa.Column(
            "model_3d_assets",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )


def downgrade():
    op.drop_column("manual_builds", "model_3d_assets")
