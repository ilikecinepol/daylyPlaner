"""calendar sync metadata and external events

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision="0002";down_revision="0001";branch_labels=None;depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind());columns={column["name"] for column in inspector.get_columns("calendar_connections")}
    if "token_expires_at" not in columns:op.add_column("calendar_connections",sa.Column("token_expires_at",sa.DateTime(timezone=True),nullable=True))
    if "status" not in columns:op.add_column("calendar_connections",sa.Column("status",sa.String(30),nullable=False,server_default="connected"))
    if "last_synced_at" not in columns:op.add_column("calendar_connections",sa.Column("last_synced_at",sa.DateTime(timezone=True),nullable=True))
    if "external_calendar_events" not in inspector.get_table_names():op.create_table("external_calendar_events",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("calendar_connection_id",sa.String(36),sa.ForeignKey("calendar_connections.id",ondelete="CASCADE"),nullable=False),
        sa.Column("external_calendar_id",sa.String(300),nullable=False,server_default="primary"),sa.Column("external_event_id",sa.String(500),nullable=False),
        sa.Column("title",sa.String(500),nullable=False,server_default=""),sa.Column("description",sa.Text(),nullable=False,server_default=""),sa.Column("location",sa.String(300),nullable=False,server_default=""),
        sa.Column("start_at",sa.DateTime(timezone=True)),sa.Column("end_at",sa.DateTime(timezone=True)),sa.Column("all_day",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("external_updated_at",sa.DateTime(timezone=True)),sa.Column("cancelled",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("calendar_connection_id","external_event_id"))
    if "ix_external_calendar_events_connection" not in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("external_calendar_events")}:op.create_index("ix_external_calendar_events_connection","external_calendar_events",["calendar_connection_id"])

def downgrade():
    op.drop_table("external_calendar_events")
    op.drop_column("calendar_connections","last_synced_at");op.drop_column("calendar_connections","status");op.drop_column("calendar_connections","token_expires_at")
