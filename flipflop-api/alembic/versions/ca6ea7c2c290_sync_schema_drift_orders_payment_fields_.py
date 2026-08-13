"""sync schema drift - orders payment fields and builds pcbuild_id

Revision ID: ca6ea7c2c290
Revises: 3348793fd2db
Create Date: 2026-08-10 00:17:23.848905

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca6ea7c2c290'
down_revision: Union[str, None] = '3348793fd2db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These columns were already recorded as applied by earlier revisions
    # (20260717_0017, 20260723_0019) but never actually landed on this
    # database, presumably from a prior manual `alembic stamp`. Guards make
    # this safe to run regardless of which pieces are actually present.
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS stripe_payment_intent_id VARCHAR")
    op.execute("ALTER TABLE orders ALTER COLUMN promised_delivery_date DROP NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_orders_stripe_payment_intent_id "
        "ON orders (stripe_payment_intent_id)"
    )

    op.execute("ALTER TABLE builds ADD COLUMN IF NOT EXISTS pcbuild_id INTEGER")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_builds_pcbuild_id'
            ) THEN
                ALTER TABLE builds
                    ADD CONSTRAINT fk_builds_pcbuild_id
                    FOREIGN KEY (pcbuild_id) REFERENCES pc_builds (id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE builds DROP CONSTRAINT IF EXISTS fk_builds_pcbuild_id")
    op.execute("ALTER TABLE builds DROP COLUMN IF EXISTS pcbuild_id")
    op.execute("DROP INDEX IF EXISTS ix_orders_stripe_payment_intent_id")
    op.execute("ALTER TABLE orders ALTER COLUMN promised_delivery_date SET NOT NULL")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS stripe_payment_intent_id")
