"""baseline schema marker

Revision ID: 0001
"""
revision="0001";down_revision=None;branch_labels=None;depends_on=None
def upgrade():
    from alembic import op
    from app.database import Base
    from app import models  # noqa: F401 - registers metadata
    Base.metadata.create_all(bind=op.get_bind())
def downgrade():pass
