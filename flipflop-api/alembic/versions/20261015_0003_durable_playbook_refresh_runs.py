"""Persist Playbook source refresh and rebuild job status across API reloads."""

from alembic import op
import sqlalchemy as sa


revision = "20261015_0003"
down_revision = "20261015_0002"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "playbook_refresh_runs" not in inspector.get_table_names():
        op.create_table(
            "playbook_refresh_runs",
            sa.Column("job_id", sa.String(length=36), primary_key=True),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("phase", sa.Text(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("heartbeat_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
        )
        inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("playbook_refresh_runs")}
    if "ix_playbook_refresh_runs_status" not in indexes:
        op.create_index("ix_playbook_refresh_runs_status", "playbook_refresh_runs", ["status"])


def downgrade():
    op.drop_index("ix_playbook_refresh_runs_status", table_name="playbook_refresh_runs")
    op.drop_table("playbook_refresh_runs")
