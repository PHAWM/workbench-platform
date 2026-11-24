from typing import Optional
from sqlmodel import SQLModel, Field


class Tenant(SQLModel, table=True):
    """Registry of tenants — lives in the public schema."""
    __tablename__ = "tenant"

    id: str = Field(primary_key=True)        # e.g. "uni_glasgow"
    display_name: str                        # e.g. "University of Glasgow"
    db_schema: str                           # Postgres schema name (same as id, explicit)
    is_active: bool = Field(default=True)
    contact_email: Optional[str] = None


class TenantCreate(SQLModel):
    id: str
    display_name: str
    contact_email: Optional[str] = None


class TenantRead(SQLModel):
    id: str
    display_name: str
    db_schema: str
    is_active: bool
    contact_email: Optional[str] = None
