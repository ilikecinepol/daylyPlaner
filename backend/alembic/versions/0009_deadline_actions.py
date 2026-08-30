"""deadline actions and processing marker

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("deadline_action", sa.String(30), nullable=False, server_default="none"))
        batch.add_column(sa.Column("deadline_processed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("deadline_processed_at")
        batch.drop_column("deadline_action")
