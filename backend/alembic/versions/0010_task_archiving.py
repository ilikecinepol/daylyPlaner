"""completed task archive policy

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision="0010"
down_revision="0009"
branch_labels=None
depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    task_columns={column["name"] for column in inspector.get_columns("tasks")}
    user_columns={column["name"] for column in inspector.get_columns("users")}
    if "archived_at" not in task_columns:op.add_column("tasks",sa.Column("archived_at",sa.DateTime(timezone=True),nullable=True))
    indexes={index["name"] for index in sa.inspect(op.get_bind()).get_indexes("tasks")}
    if "ix_tasks_archived_at" not in indexes:op.create_index("ix_tasks_archived_at","tasks",["archived_at"])
    if "completed_task_archive_policy" not in user_columns:op.add_column("users",sa.Column("completed_task_archive_policy",sa.String(30),nullable=False,server_default="never"))
    if "completed_task_archive_days" not in user_columns:op.add_column("users",sa.Column("completed_task_archive_days",sa.Integer(),nullable=False,server_default="7"))

def downgrade():
    op.drop_column("users","completed_task_archive_days")
    op.drop_column("users","completed_task_archive_policy")
    op.drop_index("ix_tasks_archived_at",table_name="tasks")
    op.drop_column("tasks","archived_at")
