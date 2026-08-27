"""step_result_metadata_json

Revision ID: d4a6e8c2f1b3
Revises: a1b2c3d4e5f6
Create Date: 2026-08-16 10:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4a6e8c2f1b3"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exec_step_results",
        sa.Column(
            "result_metadata_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("exec_step_results", "result_metadata_json")
