"""Add invoice processing idempotency key.

Revision ID: 20260824_02
Revises: 20260815_01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_02"
down_revision = "20260815_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("processing_idempotency_key", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoices", "processing_idempotency_key")
