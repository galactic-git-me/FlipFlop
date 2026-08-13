"""add motherboard_specs reference table

Revision ID: d1e5f7a2b8c3
Revises: c8b4e1a9d3f2
Create Date: 2026-08-12 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e5f7a2b8c3'
down_revision: Union[str, None] = 'c8b4e1a9d3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'motherboard_specs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('canonical_model', sa.String(length=200), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('socket', sa.String(length=30), nullable=True),
        sa.Column('chipset', sa.String(length=50), nullable=True),
        sa.Column('ram_type', sa.String(length=10), nullable=True),
        sa.Column('ram_slots', sa.Integer(), nullable=True),
        sa.Column('max_ram_gb', sa.Integer(), nullable=True),
        sa.Column('pcie_x16_slots', sa.Integer(), nullable=True),
        sa.Column('m2_slots', sa.Integer(), nullable=True),
        sa.Column('sata_ports', sa.Integer(), nullable=True),
        sa.Column('form_factor', sa.String(length=10), nullable=True),
        sa.Column('wifi', sa.Boolean(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('ai_reasoning', sa.String(length=500), nullable=True),
        sa.Column('reviewed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('raw_ai_response', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.String(length=50), nullable=False),
        sa.Column('updated_at', sa.String(length=50), nullable=False),
    )
    op.create_index('ix_motherboard_specs_canonical_model', 'motherboard_specs', ['canonical_model'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_motherboard_specs_canonical_model', table_name='motherboard_specs')
    op.drop_table('motherboard_specs')
