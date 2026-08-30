"""Personal day, week and month goals linked to ordinary tasks."""
from alembic import op
import sqlalchemy as sa

revision="0014"
down_revision="0013"
branch_labels=None
depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    if "goals" not in inspector.get_table_names():
        op.create_table("goals",
            sa.Column("id",sa.String(36),primary_key=True),
            sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
            sa.Column("title",sa.String(300),nullable=False),sa.Column("why",sa.Text(),nullable=False,server_default=""),
            sa.Column("period",sa.String(10),nullable=False),sa.Column("period_start",sa.Date(),nullable=False),sa.Column("period_end",sa.Date(),nullable=False),
            sa.Column("parent_id",sa.String(36),sa.ForeignKey("goals.id",ondelete="SET NULL")),
            sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)))
    if "ix_goals_user_id" not in {x["name"] for x in sa.inspect(op.get_bind()).get_indexes("goals")}:op.create_index("ix_goals_user_id","goals",["user_id"])
    if "goal_id" not in {x["name"] for x in sa.inspect(op.get_bind()).get_columns("tasks")}:
        with op.batch_alter_table("tasks") as batch:batch.add_column(sa.Column("goal_id",sa.String(36),sa.ForeignKey("goals.id",name="fk_tasks_goal_id_goals",ondelete="SET NULL"),nullable=True))
    if "ix_tasks_goal_id" not in {x["name"] for x in sa.inspect(op.get_bind()).get_indexes("tasks")}:op.create_index("ix_tasks_goal_id","tasks",["goal_id"])

def downgrade():
    op.drop_index("ix_tasks_goal_id",table_name="tasks")
    with op.batch_alter_table("tasks") as batch:batch.drop_column("goal_id")
    op.drop_table("goals")
