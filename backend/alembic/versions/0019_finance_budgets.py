"""finance budgets

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa

revision="0019";down_revision="0018";branch_labels=None;depends_on=None

def upgrade():
    op.create_table(
        "finance_budgets",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("name",sa.String(160),nullable=False),
        sa.Column("amount",sa.Numeric(18,2),nullable=False),
        sa.Column("currency",sa.String(3),nullable=False),
        sa.Column("category_id",sa.String(36),sa.ForeignKey("finance_categories.id",ondelete="SET NULL")),
        sa.Column("period",sa.String(20),nullable=False,server_default="monthly"),
        sa.Column("rollover",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("deleted_at",sa.DateTime(timezone=True)),
    )
    op.create_index("ix_finance_budgets_user_id","finance_budgets",["user_id"])
    op.create_index("ix_finance_budgets_category_id","finance_budgets",["category_id"])

def downgrade():
    op.drop_table("finance_budgets")
