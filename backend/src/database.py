from sqlmodel import create_engine, SQLModel, Session
from typing import Generator
import os

from dotenv import load_dotenv
from pathlib import Path

cwd = Path.cwd()
env_path = cwd / "deploy" / ".env"

load_dotenv(dotenv_path=env_path)
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB")

SQL_CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"
engine = create_engine(SQL_CONNECTION_STRING)

def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency for SQLModel sessions.
    Yields a session for each request and closes it afterwards.
    """
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    """
    Create all database tables defined in SQLModel models.
    """
    SQLModel.metadata.create_all(engine)

