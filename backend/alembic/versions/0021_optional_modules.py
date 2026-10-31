"""Optional module entitlements.

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    bind=op.get_bind()
    tables=set(sa.inspect(bind).get_table_names())
    if "module_entitlements" not in tables:
        op.create_table(
            "module_entitlements",
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("module", sa.String(length=30), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="access_code"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "module"),
        )
    if "ai_access" in tables:
        op.execute(sa.text("""
            INSERT INTO module_entitlements (user_id, module, enabled, source, expires_at)
            SELECT access.user_id, 'ai', access.enabled, 'legacy', access.expires_at
            FROM ai_access AS access
            WHERE NOT EXISTS (
                SELECT 1 FROM module_entitlements AS entitlement
                WHERE entitlement.user_id = access.user_id AND entitlement.module = 'ai'
            )
        """))


def downgrade():
    op.drop_table("module_entitlements")
