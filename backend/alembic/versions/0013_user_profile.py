"""User profile fields, preserving existing names and timezones."""
from alembic import op
import sqlalchemy as sa

revision="0013"
down_revision="0012"
branch_labels=None
depends_on=None

def upgrade():
    existing={c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    for name,kind,default in [("last_name",sa.String(120),""),("job_title",sa.String(160),""),("profile_status",sa.String(20),"available"),("contact_info",sa.String(500),""),("avatar_data_url",sa.Text(),"")]:
        if name not in existing:op.add_column("users",sa.Column(name,kind,nullable=False,server_default=default))

def downgrade():
    for name in ["avatar_data_url","contact_info","profile_status","job_title","last_name"]:op.drop_column("users",name)
