"""add timeout and retry to component steps

Revision ID: b2c4a1e9d7f3
Revises: 3f8c1f4f2a5d
Create Date: 2026-03-31 00:32:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c4a1e9d7f3"
down_revision = "3f8c1f4f2a5d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_component_steps",
        sa.Column("timeout_ms", sa.Integer(), nullable=False, server_default="15000"),
    )
    op.add_column(
        "case_component_steps",
        sa.Column("retry_times", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("case_component_steps", "timeout_ms", server_default=None)
    op.alter_column("case_component_steps", "retry_times", server_default=None)


def downgrade() -> None:
    op.drop_column("case_component_steps", "retry_times")
    op.drop_column("case_component_steps", "timeout_ms")
