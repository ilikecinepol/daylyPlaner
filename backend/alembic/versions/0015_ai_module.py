"""Optional AI module: access, conversations, proposals and usage quotas."""
from alembic import op
import sqlalchemy as sa
revision="0015"
down_revision="0014"
branch_labels=None
depends_on=None

def ident(): return sa.Column("id",sa.String(36),primary_key=True)
def owner(): return sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False)
def created(): return sa.Column("created_at",sa.DateTime(timezone=True),nullable=False)

def upgrade():
    tables=set(sa.inspect(op.get_bind()).get_table_names())
    if "ai_access" not in tables:
        op.create_table("ai_access",sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True)))
    if "ai_conversations" not in tables:
        op.create_table("ai_conversations",ident(),owner(),sa.Column("title",sa.String(120),nullable=False),created())
        op.create_index("ix_ai_conversations_user_id","ai_conversations",["user_id"])
    if "ai_requests" not in tables:
        op.create_table("ai_requests",ident(),owner(),sa.Column("conversation_id",sa.String(36),sa.ForeignKey("ai_conversations.id",ondelete="SET NULL")),
            sa.Column("request_key",sa.String(36),nullable=False),sa.Column("prompt",sa.Text(),nullable=False),sa.Column("answer",sa.Text(),nullable=False),
            sa.Column("status",sa.String(20),nullable=False),sa.Column("provider",sa.String(30),nullable=False),sa.Column("input_tokens",sa.Integer(),nullable=False),
            sa.Column("output_tokens",sa.Integer(),nullable=False),sa.Column("sources",sa.JSON(),nullable=False),created(),sa.UniqueConstraint("user_id","request_key",name="uq_ai_request_key"))
        op.create_index("ix_ai_requests_user_id","ai_requests",["user_id"])
    if "ai_proposals" not in tables:
        op.create_table("ai_proposals",ident(),sa.Column("request_id",sa.String(36),sa.ForeignKey("ai_requests.id",ondelete="CASCADE"),nullable=False),
            sa.Column("kind",sa.String(20),nullable=False),sa.Column("task_id",sa.String(36)),sa.Column("expected_version",sa.Integer()),sa.Column("before",sa.JSON(),nullable=False),
            sa.Column("changes",sa.JSON(),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("result_task_id",sa.String(36)),created())
        op.create_index("ix_ai_proposals_request_id","ai_proposals",["request_id"])
    if "ai_quotas" not in tables:
        op.create_table("ai_quotas",sa.Column("scope",sa.String(60),primary_key=True),sa.Column("day",sa.String(10),primary_key=True),sa.Column("requests",sa.Integer(),nullable=False))

def downgrade():
    for table in ["ai_proposals","ai_requests","ai_conversations","ai_quotas","ai_access"]: op.drop_table(table)
