from logging.config import fileConfig
from alembic import context
from app.database import Base,DATABASE_URL
from app import models
config=context.config;config.set_main_option("sqlalchemy.url",DATABASE_URL)
if config.config_file_name:fileConfig(config.config_file_name)
target_metadata=Base.metadata
def offline():context.configure(url=DATABASE_URL,target_metadata=target_metadata,literal_binds=True);context.run_migrations()
def online():
    from app.database import engine
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=target_metadata)
        with context.begin_transaction():context.run_migrations()
offline() if context.is_offline_mode() else online()
