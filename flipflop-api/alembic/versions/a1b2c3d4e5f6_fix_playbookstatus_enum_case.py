"""fix_playbookstatus_enum_case

Revision ID: a1b2c3d4e5f6
Revises: 573cf6989b91
Create Date: 2026-07-02 00:05:00.000000

The native Postgres enum `playbookstatus` was created with uppercase labels
(ACTIVE/DEPRECATED/RETIRED), matching SQLAlchemy's default Enum(name-based)
storage. However every query across the codebase (app/main.py,
app/api/playbooks.py, app/services/playbook_evolution.py, etc.) filters using
the lowercase PlaybookStatus.value ("active"/"deprecated"/"retired"). This
migration renames the enum labels in place to match — a metadata-only
operation that preserves existing row data.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "573cf6989b91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RENAMES = [("ACTIVE", "active"), ("DEPRECATED", "deprecated"), ("RETIRED", "retired")]


def upgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f"ALTER TYPE playbookstatus RENAME VALUE '{old}' TO '{new}'")


def downgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f"ALTER TYPE playbookstatus RENAME VALUE '{new}' TO '{old}'")
