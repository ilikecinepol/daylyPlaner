"""finance v1

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision="0018";down_revision="0017";branch_labels=None;depends_on=None

def upgrade():
    with op.batch_alter_table("goals") as b:
        b.add_column(sa.Column("target_amount",sa.Numeric(18,2),nullable=True));b.add_column(sa.Column("currency",sa.String(3),nullable=True))
    with op.batch_alter_table("projects") as b:
        b.add_column(sa.Column("budget_amount",sa.Numeric(18,2),nullable=True));b.add_column(sa.Column("budget_currency",sa.String(3),nullable=True))
    op.create_table("finance_accounts",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("type",sa.String(30),nullable=False),sa.Column("currency",sa.String(3),nullable=False),sa.Column("opening_balance",sa.Numeric(18,2),nullable=False,server_default="0"),sa.Column("is_archived",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)))
    op.create_index("ix_finance_accounts_user_id","finance_accounts",["user_id"])
    op.create_table("finance_categories",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(100),nullable=False),sa.Column("type",sa.String(10),nullable=False),sa.Column("color",sa.String(20),nullable=False),sa.Column("is_default",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("user_id","type","name"))
    op.create_index("ix_finance_categories_user_id","finance_categories",["user_id"])
    op.create_table("finance_transactions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("type",sa.String(10),nullable=False),sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("currency",sa.String(3),nullable=False),sa.Column("account_id",sa.String(36),sa.ForeignKey("finance_accounts.id",ondelete="RESTRICT"),nullable=False),sa.Column("destination_account_id",sa.String(36),sa.ForeignKey("finance_accounts.id",ondelete="RESTRICT")),sa.Column("category_id",sa.String(36),sa.ForeignKey("finance_categories.id",ondelete="SET NULL")),sa.Column("transaction_at",sa.DateTime(timezone=True),nullable=False),sa.Column("description",sa.Text(),nullable=False),sa.Column("task_id",sa.String(36),sa.ForeignKey("tasks.id",ondelete="SET NULL")),sa.Column("project_id",sa.String(36),sa.ForeignKey("projects.id",ondelete="SET NULL")),sa.Column("goal_id",sa.String(36),sa.ForeignKey("goals.id",ondelete="SET NULL")),sa.Column("goal_contribution",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)))
    for name in ["user_id","transaction_at","account_id","destination_account_id","category_id","task_id","project_id","goal_id"]:op.create_index(f"ix_finance_transactions_{name}","finance_transactions",[name])
    op.create_index("ix_finance_transactions_user_date","finance_transactions",["user_id","transaction_at"])
    op.create_table("task_finance_bindings",sa.Column("id",sa.String(36),primary_key=True),sa.Column("task_id",sa.String(36),sa.ForeignKey("tasks.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("type",sa.String(10),nullable=False),sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("currency",sa.String(3),nullable=False),sa.Column("account_id",sa.String(36),sa.ForeignKey("finance_accounts.id",ondelete="RESTRICT"),nullable=False),sa.Column("category_id",sa.String(36),sa.ForeignKey("finance_categories.id",ondelete="SET NULL")),sa.Column("transaction_id",sa.String(36),sa.ForeignKey("finance_transactions.id",ondelete="SET NULL"),unique=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("task_id","user_id"))
    op.create_index("ix_task_finance_bindings_task_id","task_finance_bindings",["task_id"]);op.create_index("ix_task_finance_bindings_user_id","task_finance_bindings",["user_id"])

def downgrade():
    op.drop_table("task_finance_bindings");op.drop_table("finance_transactions");op.drop_table("finance_categories");op.drop_table("finance_accounts")
    with op.batch_alter_table("projects") as b:b.drop_column("budget_currency");b.drop_column("budget_amount")
    with op.batch_alter_table("goals") as b:b.drop_column("currency");b.drop_column("target_amount")
