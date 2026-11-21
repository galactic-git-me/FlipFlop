"""Persist the administrator-managed approved-vendor list."""
from alembic import op
import sqlalchemy as sa

revision = "20261115_0001"
down_revision = "20261112_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "approved_vendors",
            sa.JSON(),
            nullable=False,
            server_default=sa.text('\'["eBay UK","Amazon UK","AWD-IT","Overclockers UK","Scan","Computer Orbit","Bargain Hardware","Newegg UK","Ebuyer","Very","Vinted","AliExpress","PCPartPicker UK","Google Shopping","Currys","Tesco","CCL","Box.co.uk","Corsair UK","Joybuy UK","CPC Farnell","CeX"]\''),
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "approved_vendors")
