"""task assignees and status actors

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision="0007"
down_revision="0006"
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("assigned_to_id",sa.String(36),nullable=True))
        batch.add_column(sa.Column("started_by_id",sa.String(36),nullable=True))
        batch.add_column(sa.Column("completed_by_id",sa.String(36),nullable=True))
        batch.create_foreign_key("fk_tasks_assigned_to","users",["assigned_to_id"],["id"],ondelete="SET NULL")
        batch.create_foreign_key("fk_tasks_started_by","users",["started_by_id"],["id"],ondelete="SET NULL")
        batch.create_foreign_key("fk_tasks_completed_by","users",["completed_by_id"],["id"],ondelete="SET NULL")
        batch.create_index("ix_tasks_assigned_to_id",["assigned_to_id"])

def downgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_assigned_to_id")
        batch.drop_constraint("fk_tasks_completed_by",type_="foreignkey")
        batch.drop_constraint("fk_tasks_started_by",type_="foreignkey")
        batch.drop_constraint("fk_tasks_assigned_to",type_="foreignkey")
        batch.drop_column("completed_by_id")
        batch.drop_column("started_by_id")
        batch.drop_column("assigned_to_id")
