"""Add durable agent handoffs and Steam monthly snapshot provenance."""
from alembic import op
import sqlalchemy as sa


revision = "20261116_0001"
down_revision = "20261115_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("steam_hardware_stats", sa.Column("observation_month", sa.String(7), nullable=True))
    op.add_column("steam_hardware_stats", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("steam_hardware_stats", sa.Column("parser_version", sa.String(64), nullable=True))
    op.add_column("steam_hardware_stats", sa.Column("geography", sa.String(32), nullable=True))
    op.add_column("steam_hardware_stats", sa.Column("platform_filter", sa.String(64), nullable=True))
    op.create_index("ix_steam_hardware_stats_observation_month", "steam_hardware_stats", ["observation_month"])

    # Development startup can create this table from ORM metadata before
    # Alembic records the migration. Reconcile the two columns added to the
    # persisted event contract before asking Alembic to adopt the table.
    if sa.inspect(op.get_bind()).has_table("agent_handoff_events"):
        existing_columns = {
            column["name"] for column in sa.inspect(op.get_bind()).get_columns("agent_handoff_events")
        }
        if "processing_status" not in existing_columns:
            op.add_column(
                "agent_handoff_events",
                sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
            )
        if "processed_at" not in existing_columns:
            op.add_column("agent_handoff_events", sa.Column("processed_at", sa.DateTime(), nullable=True))

    op.create_table(
        "agent_handoff_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("producer", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_agent_handoff_events_type", "agent_handoff_events", ["event_type"])
    op.create_index("ix_agent_handoff_events_producer", "agent_handoff_events", ["producer"])
    op.create_index("ix_agent_handoff_events_occurred_at", "agent_handoff_events", ["occurred_at"])
    op.create_index("ix_agent_handoff_events_type_occurred", "agent_handoff_events", ["event_type", "occurred_at"])
    op.create_index("ix_agent_handoff_events_correlation", "agent_handoff_events", ["correlation_id"])
    op.create_index("ix_agent_handoff_events_processing_status", "agent_handoff_events", ["processing_status"])


def downgrade() -> None:
    op.drop_index("ix_agent_handoff_events_correlation", table_name="agent_handoff_events")
    op.drop_index("ix_agent_handoff_events_processing_status", table_name="agent_handoff_events")
    op.drop_index("ix_agent_handoff_events_type_occurred", table_name="agent_handoff_events")
    op.drop_index("ix_agent_handoff_events_occurred_at", table_name="agent_handoff_events")
    op.drop_index("ix_agent_handoff_events_producer", table_name="agent_handoff_events")
    op.drop_index("ix_agent_handoff_events_type", table_name="agent_handoff_events")
    op.drop_table("agent_handoff_events")
    op.drop_index("ix_steam_hardware_stats_observation_month", table_name="steam_hardware_stats")
    for column in ("platform_filter", "geography", "parser_version", "source_url", "observation_month"):
        op.drop_column("steam_hardware_stats", column)
