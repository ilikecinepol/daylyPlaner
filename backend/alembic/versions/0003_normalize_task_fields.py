"""normalize task scheduling fields

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision="0003";down_revision="0002";branch_labels=None;depends_on=None

def upgrade():
    # Copy legacy values before removing the old sources of truth.
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("tasks")}
    if "duration" in columns:op.execute("UPDATE tasks SET duration_minutes = duration WHERE duration_minutes IS NULL")
    if "completed" in columns:
        op.execute("UPDATE tasks SET status = 'completed' WHERE completed = true AND status != 'completed'")
        op.execute("UPDATE tasks SET completed_at = CURRENT_TIMESTAMP WHERE completed = true AND completed_at IS NULL")
    with op.batch_alter_table("tasks") as batch:
        for name in ("date","time","duration","completed","column_name"):
            if name in columns:batch.drop_column(name)

def downgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("date",sa.String(10),nullable=False,server_default=""));batch.add_column(sa.Column("time",sa.String(5),nullable=False,server_default=""));batch.add_column(sa.Column("duration",sa.Integer(),nullable=False,server_default="60"));batch.add_column(sa.Column("completed",sa.Boolean(),nullable=False,server_default=sa.false()));batch.add_column(sa.Column("column_name",sa.String(80),nullable=False,server_default="Запланировано"))
