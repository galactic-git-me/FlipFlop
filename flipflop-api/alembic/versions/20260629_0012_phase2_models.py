"""Add Phase 2 core business models (OSComponent, DesktopTheme, WelcomeGuide)

Revision ID: 20260629_0012
Revises: 20260629_0011
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError


revision = "20260629_0012"
down_revision = "20260629_0011"
depends_on = None


def upgrade():
    # Create os_components table if it doesn't exist
    try:
        op.create_table(
            'os_components',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('os_type', sa.String(50), nullable=False, index=True),
            sa.Column('license_key', sa.String(255), nullable=False),
            sa.Column('assigned_to_order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=True),
            sa.Column('purchased_cost', sa.Float(), nullable=False),
            sa.Column('resale_price', sa.Float(), nullable=False),
            sa.Column('status', sa.String(50), default='available', nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Index('idx_os_components_os_type', 'os_type'),
            sa.Index('idx_os_components_status', 'status'),
        )
    except OperationalError:
        # Table already exists, skip creation
        pass

    # Create desktop_themes table if it doesn't exist
    try:
        op.create_table(
            'desktop_themes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(255), unique=True, nullable=False, index=True),
            sa.Column('rainmeter_config_path', sa.String(500), nullable=False),
            sa.Column('desktop_background_path', sa.String(500), nullable=False),
            sa.Column('preview_image_path', sa.String(500)),
            sa.Column('description', sa.Text()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Index('idx_desktop_themes_name', 'name'),
        )
    except OperationalError:
        # Table already exists, skip creation
        pass

    # Create welcome_guides table if it doesn't exist
    try:
        op.create_table(
            'welcome_guides',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), unique=True, nullable=False),
            sa.Column('pdf_blob', sa.LargeBinary()),
            sa.Column('generated_at', sa.DateTime()),
            sa.Column('content_json', sa.JSON()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Index('idx_welcome_guides_order_id', 'order_id'),
        )
    except OperationalError:
        # Table already exists, skip creation
        pass

    # Add theme_id column to orders table if it doesn't exist
    try:
        op.add_column('orders', sa.Column('theme_id', sa.Integer(), sa.ForeignKey('desktop_themes.id'), nullable=True))
    except OperationalError:
        # Column already exists, skip
        pass

    # Add indexes on orders foreign keys
    try:
        op.create_index('idx_orders_theme_id', 'orders', ['theme_id'])
    except OperationalError:
        # Index already exists, skip
        pass


def downgrade():
    # Drop indexes on orders if they exist
    try:
        op.drop_index('idx_orders_theme_id', table_name='orders')
    except OperationalError:
        pass

    # Drop columns from orders if they exist
    try:
        op.drop_column('orders', 'theme_id')
    except OperationalError:
        pass

    # Drop tables
    try:
        op.drop_table('welcome_guides')
    except OperationalError:
        pass

    try:
        op.drop_table('desktop_themes')
    except OperationalError:
        pass

    try:
        op.drop_table('os_components')
    except OperationalError:
        pass
