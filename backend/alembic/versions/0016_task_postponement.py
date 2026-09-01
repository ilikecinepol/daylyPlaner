"""Track tasks postponed until a date or indefinitely."""
from alembic import op
import sqlalchemy as sa

revision="0016"
down_revision="0014"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("tasks",sa.Column("postponed_at",sa.DateTime(timezone=True),nullable=True))
    op.create_index("ix_tasks_postponed_at","tasks",["postponed_at"])

def downgrade():
    op.drop_index("ix_tasks_postponed_at",table_name="tasks")
    op.drop_column("tasks","postponed_at")
