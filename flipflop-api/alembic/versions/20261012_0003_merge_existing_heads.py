"""Join the existing independent migration branches for a single release head."""

revision = "20261012_merge_heads"
down_revision = (
    "20260921_0003",
    "20261012_0002",
)
# Only independent heads belong here. Listing their ancestors as additional
# parents makes Alembic attempt to remove heads that were already consumed.
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
