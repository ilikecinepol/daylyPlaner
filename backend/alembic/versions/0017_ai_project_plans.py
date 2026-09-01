"""Store atomic AI project-plan results."""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("ai_proposals")}
    if "result" not in columns:
        with op.batch_alter_table("ai_proposals") as batch:
            batch.add_column(sa.Column("result", sa.JSON(), nullable=True))

def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("ai_proposals")}
    if "result" in columns:
        with op.batch_alter_table("ai_proposals") as batch:
            batch.drop_column("result")
