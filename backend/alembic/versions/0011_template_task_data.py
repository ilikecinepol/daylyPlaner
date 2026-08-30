"""store complete task template payload

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision="0011"
down_revision="0010"
branch_labels=None
depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("task_templates")}
    if "task_data" not in columns:op.add_column("task_templates",sa.Column("task_data",sa.JSON(),nullable=False,server_default="{}"))

def downgrade():
    op.drop_column("task_templates","task_data")
