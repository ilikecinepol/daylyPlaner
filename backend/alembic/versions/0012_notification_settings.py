"""notification settings and clear marker

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision="0012"
down_revision="0011"
branch_labels=None
depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "notification_settings" not in columns:op.add_column("users",sa.Column("notification_settings",sa.JSON(),nullable=False,server_default="{}"))
    if "notifications_cleared_at" not in columns:op.add_column("users",sa.Column("notifications_cleared_at",sa.DateTime(timezone=True),nullable=True))

def downgrade():
    op.drop_column("users","notifications_cleared_at")
    op.drop_column("users","notification_settings")
