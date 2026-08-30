"""separate calendar end from task deadline

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("end_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_tasks_deadline_at", ["deadline_at"])
    # due_at historically meant the end of a calendar block, never a deadline.
    op.execute("UPDATE tasks SET end_at = due_at WHERE due_at IS NOT NULL")


def downgrade():
    op.execute("UPDATE tasks SET due_at = end_at WHERE end_at IS NOT NULL")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_deadline_at")
        batch.drop_column("deadline_at")
        batch.drop_column("end_at")
