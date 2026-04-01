"""為 retrieval evaluation runs 新增 profile 與 config snapshot。"""

from alembic import op
import sqlalchemy as sa


revision = "20260401_0013"
down_revision = "20260401_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 evaluation benchmark profile 與 config snapshot 欄位。"""

    op.add_column(
        "retrieval_eval_runs",
        sa.Column("evaluation_profile", sa.String(length=64), nullable=False, server_default="production_like_v1"),
    )
    op.add_column(
        "retrieval_eval_runs",
        sa.Column("config_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.alter_column("retrieval_eval_runs", "evaluation_profile", server_default=None)
    op.alter_column("retrieval_eval_runs", "config_snapshot_json", server_default=None)


def downgrade() -> None:
    """移除 evaluation benchmark profile 與 config snapshot 欄位。"""

    op.drop_column("retrieval_eval_runs", "config_snapshot_json")
    op.drop_column("retrieval_eval_runs", "evaluation_profile")
