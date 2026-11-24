from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy import text
from typing import Generator
import re
import os

from dotenv import load_dotenv
from pathlib import Path

cwd = Path.cwd()
# ENV_FILE env var lets callers override which .env is loaded (e.g. multi-tenant).
# Falls back to deploy/.env for backwards compatibility.
_env_file = os.getenv("ENV_FILE", "deploy/.env")
env_path = cwd / _env_file

load_dotenv(dotenv_path=env_path, override=False)
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB")

SQL_CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Default engine — public schema (tenant registry, superuser ops)
engine = create_engine(SQL_CONNECTION_STRING)

# ---------------------------------------------------------------------------
# Multi-tenant engine cache
# ---------------------------------------------------------------------------

_tenant_engines: dict = {}
_SCHEMA_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")  # safe schema names only


def _validate_schema_name(schema: str) -> str:
    """Reject schema names that could cause SQL injection."""
    if not _SCHEMA_RE.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")
    return schema


def get_tenant_engine(tenant_schema: str):
    """Return a cached engine for the given tenant schema."""
    _validate_schema_name(tenant_schema)
    if tenant_schema not in _tenant_engines:
        _tenant_engines[tenant_schema] = create_engine(
            SQL_CONNECTION_STRING,
            pool_size=5,
            max_overflow=10,
            connect_args={"options": f"-csearch_path={tenant_schema},public"},
        )
    return _tenant_engines[tenant_schema]


def get_tenant_schema_from_request(request) -> str | None:
    """Extract tenant schema from X-Tenant-ID header. Returns None if not present.

    The header is lowercased because Postgres schema names in this app are
    always lowercase (see _SCHEMA_RE), but invitation links and clients have
    been observed sending mixed-case values (e.g. "WDHSCP_Magic_Notes_26").
    """
    value = request.headers.get("X-Tenant-ID")
    return value.lower() if value else None


def get_session_for_schema(schema: str | None) -> Generator[Session, None, None]:
    """
    Return a session scoped to *schema*.
    If schema is None, falls back to the public schema (superuser ops).
    """
    if schema:
        tenant_engine = get_tenant_engine(schema)
        with Session(tenant_engine) as session:
            yield session
    else:
        with Session(engine) as session:
            yield session


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency for SQLModel sessions (public schema — no tenant).
    Yields a session for each request and closes it afterwards.
    """
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """
    Create all database tables defined in SQLModel models.
    """
    SQLModel.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Tenant provisioning
# ---------------------------------------------------------------------------

def provision_tenant_schema(schema_name: str) -> None:
    """
    Create a Postgres schema and run all table migrations inside it.
    Call this when registering a new tenant.
    """
    _validate_schema_name(schema_name)

    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        conn.commit()

    # Run Alembic migrations scoped to the new schema.
    # We pass the tenant engine via attributes to avoid configparser % interpolation
    # issues that arise when setting a URL with encoded characters via set_main_option.
    from alembic.config import Config
    from alembic import command

    tenant_engine = create_engine(
        SQL_CONNECTION_STRING,
        connect_args={"options": f"-csearch_path={schema_name},public"},
    )
    alembic_cfg = Config("alembic.ini")
    conn = tenant_engine.connect()
    alembic_cfg.attributes["connection"] = conn
    alembic_cfg.attributes["version_table_schema"] = schema_name
    command.upgrade(alembic_cfg, "head")
    conn.close()

