"""baseline_adoption_traceability

Revision ID: 3f8c1f4f2a5d
Revises: 8d4f52f7d9f1
Create Date: 2026-03-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f8c1f4f2a5d"
down_revision: Union[str, Sequence[str], None] = "8d4f52f7d9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset_baseline_revisions",
        sa.Column("source_report_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
    )
    op.add_column(
        "asset_baseline_revisions",
        sa.Column("source_case_run_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
    )
    op.add_column(
        "asset_baseline_revisions",
        sa.Column("source_step_result_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_asset_baseline_revisions_source_report_id_report_run_reports"),
        "asset_baseline_revisions",
        "report_run_reports",
        ["source_report_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_asset_baseline_revisions_source_case_run_id_exec_test_case_runs"),
        "asset_baseline_revisions",
        "exec_test_case_runs",
        ["source_case_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_asset_baseline_revisions_source_step_result_id_exec_step_results"),
        "asset_baseline_revisions",
        "exec_step_results",
        ["source_step_result_id"],
        ["id"],
    )
    op.create_index(
        "ix_asset_baseline_revisions_source_report",
        "asset_baseline_revisions",
        ["source_report_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_baseline_revisions_source_case_run",
        "asset_baseline_revisions",
        ["source_case_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_baseline_revisions_source_step_result",
        "asset_baseline_revisions",
        ["source_step_result_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_asset_baseline_revisions_source_step_result", table_name="asset_baseline_revisions")
    op.drop_index("ix_asset_baseline_revisions_source_case_run", table_name="asset_baseline_revisions")
    op.drop_index("ix_asset_baseline_revisions_source_report", table_name="asset_baseline_revisions")
    op.drop_constraint(
        op.f("fk_asset_baseline_revisions_source_step_result_id_exec_step_results"),
        "asset_baseline_revisions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_asset_baseline_revisions_source_case_run_id_exec_test_case_runs"),
        "asset_baseline_revisions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_asset_baseline_revisions_source_report_id_report_run_reports"),
        "asset_baseline_revisions",
        type_="foreignkey",
    )
    op.drop_column("asset_baseline_revisions", "source_step_result_id")
    op.drop_column("asset_baseline_revisions", "source_case_run_id")
    op.drop_column("asset_baseline_revisions", "source_report_id")
