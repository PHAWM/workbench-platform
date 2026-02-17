import os
import re
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context

from dotenv import load_dotenv

# Load the .env file from the project root (adjust path as needed)
load_dotenv()

# this is the Alembic Config object, which provides access to the .ini file values
config = context.config

# Interpret the config file for Python logging
fileConfig(config.config_file_name)

# Import your SQLAlchemy models here and set the target metadata for autogenerate support
# For example:
# from your_project.models import Base
# target_metadata = Base.metadata

from src.models import *
from sqlmodel import create_engine, SQLModel, Session

target_metadata = SQLModel.metadata  # Replace with your actual metadata
# target_metadata = None

def get_url():
    """
    Construct the SQLAlchemy database URL dynamically from environment variables.
    """
    user = os.getenv("POSTGRES_USER", "")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "")
    db = os.getenv("POSTGRES_DB", "")
    url = f"postgresql://{user}:{password}@{host}/{db}"

    return url

def run_migrations_offline():
    """
    Run migrations in 'offline' mode.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """
    Run migrations in 'online' mode.
    """
    url = get_url()

    # Set the URL in Alembic config to keep it consistent
    config.set_main_option("sqlalchemy.url", url)

    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
