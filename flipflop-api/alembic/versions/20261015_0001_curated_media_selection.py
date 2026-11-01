"""Persist explicit curated catalogue photo/video selections."""
from alembic import op
import sqlalchemy as sa

revision = "20261015_0001"
down_revision = "20261014_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("curated_bestseller_reviews", sa.Column("selected_media", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("curated_bestseller_reviews", "selected_media")
