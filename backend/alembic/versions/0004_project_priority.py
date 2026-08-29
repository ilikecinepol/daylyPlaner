"""add project priority"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("projects")}
    if "priority" not in columns:op.add_column("projects", sa.Column("priority", sa.String(length=2), nullable=False, server_default="P3"))

def downgrade():
    op.drop_column("projects", "priority")
