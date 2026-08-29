"""add project-independent direct chats"""
from alembic import op
import sqlalchemy as sa

revision="0005"
down_revision="0004"
branch_labels=None
depends_on=None

def upgrade():
    tables=set(sa.inspect(op.get_bind()).get_table_names())
    if "direct_chats" not in tables:
        op.create_table("direct_chats",sa.Column("id",sa.String(36),primary_key=True),sa.Column("created_by",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_direct_chats_created_by","direct_chats",["created_by"])
    if "direct_chat_members" not in tables:
        op.create_table("direct_chat_members",sa.Column("id",sa.String(36),primary_key=True),sa.Column("chat_id",sa.String(36),sa.ForeignKey("direct_chats.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("joined_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("chat_id","user_id"));op.create_index("ix_direct_chat_members_chat_id","direct_chat_members",["chat_id"]);op.create_index("ix_direct_chat_members_user_id","direct_chat_members",["user_id"])
    if "direct_messages" not in tables:
        op.create_table("direct_messages",sa.Column("id",sa.String(36),primary_key=True),sa.Column("chat_id",sa.String(36),sa.ForeignKey("direct_chats.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True),nullable=True));op.create_index("ix_direct_messages_chat_id","direct_messages",["chat_id"]);op.create_index("ix_direct_messages_user_id","direct_messages",["user_id"])

def downgrade():
    op.drop_table("direct_messages");op.drop_table("direct_chat_members");op.drop_table("direct_chats")
