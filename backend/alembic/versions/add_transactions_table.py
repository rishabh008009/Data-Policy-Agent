"""Add transactions table for IBM AML dataset

Revision ID: a1b2c3d4e5f6
Revises: 5be26697276d
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "5be26697276d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_bank", sa.String(255), nullable=False),
        sa.Column("from_account", sa.String(255), nullable=False),
        sa.Column("to_bank", sa.String(255), nullable=False),
        sa.Column("to_account", sa.String(255), nullable=False),
        sa.Column("amount_paid", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_currency", sa.String(50), nullable=False),
        sa.Column("amount_received", sa.Numeric(18, 2), nullable=False),
        sa.Column("receiving_currency", sa.String(50), nullable=False),
        sa.Column("payment_format", sa.String(100), nullable=False),
        sa.Column("is_laundering", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_transactions_from_account", "transactions", ["from_account"])
    op.create_index("ix_transactions_to_account", "transactions", ["to_account"])
    op.create_index("ix_transactions_timestamp", "transactions", ["timestamp"])
    op.create_index("ix_transactions_is_laundering", "transactions", ["is_laundering"])


def downgrade() -> None:
    op.drop_table("transactions")
