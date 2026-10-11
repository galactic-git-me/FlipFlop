"""Encrypt existing Windows licence keys at rest.

Revision ID: 20260929_0013
Revises: 20260929_0012
"""
from alembic import op
import sqlalchemy as sa

from app.services.license_key_crypto import decrypt_license_key, encrypt_license_key


revision = "20260929_0013"
down_revision = "20260929_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, license_key FROM os_components")).mappings().all()
    for row in rows:
        current = row["license_key"]
        if current and not str(current).startswith("enc:v1:"):
            connection.execute(
                sa.text("UPDATE os_components SET license_key = :license_key WHERE id = :id"),
                {"id": row["id"], "license_key": encrypt_license_key(str(current))},
            )


def downgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, license_key FROM os_components")).mappings().all()
    for row in rows:
        current = row["license_key"]
        if current and str(current).startswith("enc:v1:"):
            connection.execute(
                sa.text("UPDATE os_components SET license_key = :license_key WHERE id = :id"),
                {"id": row["id"], "license_key": decrypt_license_key(str(current))},
            )
