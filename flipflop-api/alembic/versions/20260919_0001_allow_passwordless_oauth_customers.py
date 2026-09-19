"""Allow customers created through OAuth to omit a local password."""

from alembic import op


revision = "20260919_0001"
down_revision = "20260917_0002"
depends_on = None


def upgrade():
    op.alter_column("customers", "password_hash", nullable=True)


def downgrade():
    op.alter_column("customers", "password_hash", nullable=False)
