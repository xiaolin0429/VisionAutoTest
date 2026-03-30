"""report_artifact_links

Revision ID: 8d4f52f7d9f1
Revises: c5bd66b5f125
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d4f52f7d9f1"
down_revision: Union[str, Sequence[str], None] = "c5bd66b5f125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "report_artifacts",
        sa.Column("case_run_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
    )
    op.add_column(
        "report_artifacts",
        sa.Column("step_result_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_report_artifacts_case_run_id_exec_test_case_runs"),
        "report_artifacts",
        "exec_test_case_runs",
        ["case_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_report_artifacts_step_result_id_exec_step_results"),
        "report_artifacts",
        "exec_step_results",
        ["step_result_id"],
        ["id"],
    )
    op.create_index(
        "ix_report_artifacts_report_artifact_type",
        "report_artifacts",
        ["report_id", "artifact_type"],
        unique=False,
    )
    op.create_index(
        "ix_report_artifacts_report_case_run",
        "report_artifacts",
        ["report_id", "case_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_report_artifacts_report_step_result",
        "report_artifacts",
        ["report_id", "step_result_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_report_artifacts_report_step_result", table_name="report_artifacts")
    op.drop_index("ix_report_artifacts_report_case_run", table_name="report_artifacts")
    op.drop_index("ix_report_artifacts_report_artifact_type", table_name="report_artifacts")
    op.drop_constraint(op.f("fk_report_artifacts_step_result_id_exec_step_results"), "report_artifacts", type_="foreignkey")
    op.drop_constraint(op.f("fk_report_artifacts_case_run_id_exec_test_case_runs"), "report_artifacts", type_="foreignkey")
    op.drop_column("report_artifacts", "step_result_id")
    op.drop_column("report_artifacts", "case_run_id")
