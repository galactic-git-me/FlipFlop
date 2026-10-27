"""Expand Gem Radar CPK columns to the model's 64-character contract."""
from alembic import op
import sqlalchemy as sa


revision = "20261027_0001"
down_revision = "20261026_0001"
branch_labels = None
depends_on = None


def _existing_cpk_tables() -> list[str]:
    inspector = sa.inspect(op.get_bind())
    return [
        table
        for table in ("gem_radar_scored_listings", "cpk_pricing_index")
        if inspector.has_table(table, schema="public")
        and any(column["name"] == "cpk" for column in inspector.get_columns(table, schema="public"))
    ]


def upgrade() -> None:
    for table in _existing_cpk_tables():
        op.execute(f"ALTER TABLE public.{table} ALTER COLUMN cpk TYPE VARCHAR(64)")


def downgrade() -> None:
    connection = op.get_bind()
    for table in _existing_cpk_tables():
        has_long_values = connection.execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM public.{table} WHERE cpk IS NOT NULL AND length(cpk) > 16)"
        )).scalar_one()
        if has_long_values:
            raise RuntimeError(f"Cannot narrow {table}.cpk to VARCHAR(16): longer values exist")
        op.execute(f"ALTER TABLE public.{table} ALTER COLUMN cpk TYPE VARCHAR(16)")
