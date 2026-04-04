"""conditional_branch_step_result_metadata

Revision ID: f3c9d7b1a2e4
Revises: e7b3c1a4d9f2
Create Date: 2026-04-05 10:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3c9d7b1a2e4"
down_revision = "e7b3c1a4d9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exec_step_results",
        sa.Column("parent_step_no", sa.Integer(), nullable=True),
    )
    op.add_column(
        "exec_step_results",
        sa.Column("branch_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "exec_step_results",
        sa.Column("branch_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "exec_step_results",
        sa.Column("branch_step_index", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exec_step_results", "branch_step_index")
    op.drop_column("exec_step_results", "branch_name")
    op.drop_column("exec_step_results", "branch_key")
    op.drop_column("exec_step_results", "parent_step_no")
