"""Persist manual-build creation origin on existing installations.

Revision ID: 20261020_0001
Revises: 20261019_0001

The original column existed only in a disabled startup migration. All ORM
queries of ManualBuild (including delivery follow-up) require it.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261020_0001"
down_revision = "20261019_0001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("manual_builds"):
        raise RuntimeError("Cannot add creation origin: manual_builds table is missing")
    existing = next((column for column in inspector.get_columns("manual_builds") if column["name"] == "creation_method"), None)
    if existing is not None:
        if not isinstance(existing["type"], sa.String) or existing["type"].length != 20:
            raise RuntimeError("Existing manual_builds.creation_method must be VARCHAR(20); no data was changed")
        return
    op.add_column("manual_builds", sa.Column("creation_method", sa.String(20), nullable=False, server_default="manual"))


def downgrade():
    # Older application code ignores this additive column. Dropping it would
    # destroy the recorded distinction between manual and AI-created builds.
    raise RuntimeError("Keep the additive creation_method column when rolling application code back; removing it would lose build origin history")
