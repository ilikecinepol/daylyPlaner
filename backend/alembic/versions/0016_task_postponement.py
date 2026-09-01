"""Track tasks postponed until a date or indefinitely."""
from alembic import op
import sqlalchemy as sa

revision="0016"
down_revision="0015"
branch_labels=None
depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    columns={column["name"] for column in inspector.get_columns("tasks")}
    indexes={index["name"] for index in inspector.get_indexes("tasks")}
    if "postponed_at" not in columns:
        op.add_column("tasks",sa.Column("postponed_at",sa.DateTime(timezone=True),nullable=True))
    if "ix_tasks_postponed_at" not in indexes:
        op.create_index("ix_tasks_postponed_at","tasks",["postponed_at"])

def downgrade():
    inspector=sa.inspect(op.get_bind())
    if "ix_tasks_postponed_at" in {index["name"] for index in inspector.get_indexes("tasks")}:
        op.drop_index("ix_tasks_postponed_at",table_name="tasks")
    if "postponed_at" in {column["name"] for column in inspector.get_columns("tasks")}:
        op.drop_column("tasks","postponed_at")
