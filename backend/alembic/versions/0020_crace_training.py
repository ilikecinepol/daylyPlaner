"""CRACE training module

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crace_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight_kg", sa.Numeric(6, 2)),
        sa.Column("max_hr", sa.Integer(), nullable=False, server_default="190"),
        sa.Column("race_date", sa.Date(), nullable=False),
        sa.Column("completed_sessions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_crace_profiles_user_id", "crace_profiles", ["user_id"])
    op.create_table(
        "crace_workouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_key", sa.String(40)),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_hr", sa.Integer()),
        sa.Column("max_hr", sa.Integer()),
        sa.Column("rpe", sa.Integer()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("samples", sa.JSON(), nullable=False),
        sa.Column("laps", sa.JSON(), nullable=False),
    )
    op.create_index("ix_crace_workouts_user_id", "crace_workouts", ["user_id"])
    op.create_index("ix_crace_workouts_user_started", "crace_workouts", ["user_id", "started_at"])


def downgrade():
    op.drop_table("crace_workouts")
    op.drop_table("crace_profiles")
