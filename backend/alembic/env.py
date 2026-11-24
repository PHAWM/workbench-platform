import os
import re
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context

from dotenv import load_dotenv

# Respect ENV_FILE env var so the multi-tenant env can be loaded.
# Falls back to deploy/.env for backwards compatibility.
_env_file = os.getenv("ENV_FILE", "deploy/.env")
load_dotenv(dotenv_path=_env_file, override=False)

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

# Tables that belong exclusively in the public schema (platform-level).
_PUBLIC_ONLY_TABLES = {"tenant"}

# Tables that belong exclusively in tenant schemas (never in public).
# "tenant" must not be replicated into every tenant schema.
_TENANT_EXCLUDED_TABLES = {"tenant"}


def _make_include_name(target_schema: str | None):
    """
    Return an include_name callback for Alembic's autogenerate.

    When migrating the public schema: only create/manage public-only tables.
    When migrating a tenant schema: create everything except public-only tables.
    """
    def include_name(name, type_, parent_names):
        if type_ == "schema":
            return True
        if type_ == "table":
            if target_schema is None or target_schema == "public":
                # Public schema — only manage tables that belong there
                return name in _PUBLIC_ONLY_TABLES or name == "user"
            else:
                # Tenant schema — manage everything except tenant registry
                return name not in _TENANT_EXCLUDED_TABLES
        return True
    return include_name


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
    Run migrations in 'offline' mode (public schema only).
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_name=_make_include_name("public"),
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """
    Run migrations in 'online' mode.
    """
    # When called from provision_tenant_schema, a pre-built connection is passed
    # via config.attributes to avoid configparser % interpolation issues with
    # URL-encoded search_path options.
    pre_existing_conn = config.attributes.get("connection", None)

    if pre_existing_conn is not None:
        version_table_schema = config.attributes.get("version_table_schema", None)
        # tenant schema name is the version_table_schema value
        tenant_schema = version_table_schema
        context.configure(
            connection=pre_existing_conn,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            version_table_schema=version_table_schema,
            include_name=_make_include_name(tenant_schema),
        )
        with context.begin_transaction():
            context.run_migrations()
        return

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
            include_name=_make_include_name("public"),
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
