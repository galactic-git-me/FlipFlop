"""Join the existing independent migration branches for a single release head."""

revision = "20261012_merge_heads"
down_revision = (
    "20260629_0013",
    "20260727_0023",
    "20260805_0025",
    "20260806_0001",
    "20260806_0002",
    "20260809_0001",
    "20260809_0005",
    "20260819_0004",
    "20260913_0001",
    "20260921_0003",
    "20260925_0003",
    "vnext_20260928_07",
    "20260930_0017",
    "20261012_0002",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
