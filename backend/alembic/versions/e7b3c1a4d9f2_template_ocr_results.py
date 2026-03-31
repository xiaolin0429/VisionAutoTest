"""template_ocr_results

Revision ID: e7b3c1a4d9f2
Revises: b2c4a1e9d7f3
Create Date: 2026-03-31 16:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7b3c1a4d9f2"
down_revision = "b2c4a1e9d7f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_template_ocr_results",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("template_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("baseline_revision_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("source_media_object_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("engine_name", sa.String(length=64), nullable=False),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["baseline_revision_id"],
            ["asset_baseline_revisions.id"],
            name=op.f("fk_asset_template_ocr_results_baseline_revision_id_asset_baseline_revisions"),
        ),
        sa.ForeignKeyConstraint(
            ["source_media_object_id"],
            ["asset_media_objects.id"],
            name=op.f("fk_asset_template_ocr_results_source_media_object_id_asset_media_objects"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["asset_templates.id"],
            name=op.f("fk_asset_template_ocr_results_template_id_asset_templates"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_template_ocr_results")),
        sa.UniqueConstraint("template_id", "baseline_revision_id", name="uk_asset_template_ocr_results"),
    )


def downgrade() -> None:
    op.drop_table("asset_template_ocr_results")
