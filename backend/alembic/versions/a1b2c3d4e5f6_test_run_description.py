"""test_run_description

Revision ID: a1b2c3d4e5f6
Revises: f3c9d7b1a2e4
Create Date: 2026-04-06 10:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f3c9d7b1a2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exec_test_runs",
        sa.Column("description", sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exec_test_runs", "description")
