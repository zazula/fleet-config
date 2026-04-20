from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_feature_flags"
down_revision = "0002_config_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rollout_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rules", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_feature_flags_name"),
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
