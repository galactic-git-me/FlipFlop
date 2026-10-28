"""Persist additive release fields previously handled only during app startup."""
from alembic import op
import sqlalchemy as sa
revision='20261028_0001'
down_revision='20261027_0002'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    for table,column in [
        ('app_settings',sa.Column('storefront_trust_messages',sa.JSON(),nullable=False,server_default='[]')),
        ('app_settings',sa.Column('storefront_trust_message_seconds',sa.Integer(),nullable=False,server_default='6')),
        ('manual_builds',sa.Column('ebay_ship_by_date',sa.DateTime(),nullable=True)),
        # Legacy listing-price records must remain intact. Their unknown build
        # attribution stays NULL; new build-price writes supply these fields.
        ('price_history',sa.Column('manual_build_id',sa.Integer(),sa.ForeignKey('manual_builds.id'),nullable=True)),
        ('price_history',sa.Column('price_gbp',sa.Integer(),nullable=True)),
        ('price_history',sa.Column('reason',sa.String(100),nullable=True)),
        ('price_history',sa.Column('previous_price_gbp',sa.Integer(),nullable=True)),
    ]:
        if column.name not in {c['name'] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table,column)

def downgrade():
    raise RuntimeError('Release fields contain persistent data; restore the pre-release backup for rollback')
