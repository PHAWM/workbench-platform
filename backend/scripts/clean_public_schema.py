#!/usr/bin/env python3
"""
Drop all application tables from the public schema, keeping only the
platform-level tables: tenant, user, alembic_version.

Alembic's upgrade command creates all tables in whatever schema the
connection points at. For the multi-tenant setup, alembic upgrade head
runs against public (default search_path), which creates every table
there. This script tidies that up so public stays minimal.

Safe to run multiple times (tables that are already gone are silently skipped).
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, inspect
from src.database import engine

# Tables that legitimately belong in public
PUBLIC_KEEP = {"tenant", "user", "alembic_version"}


def main():
    with engine.connect() as conn:
        inspector = inspect(conn)
        all_tables = inspector.get_table_names(schema="public")
        to_drop = [t for t in all_tables if t not in PUBLIC_KEEP]

        if not to_drop:
            print("public schema is already clean — nothing to drop.")
            return

        print(f"Dropping {len(to_drop)} app tables from public schema...")
        # CASCADE handles foreign-key dependencies between tables
        conn.execute(
            text(
                "DROP TABLE IF EXISTS "
                + ", ".join(f'public."{t}"' for t in to_drop)
                + " CASCADE"
            )
        )
        conn.commit()
        print(f"Done. Kept: {sorted(PUBLIC_KEEP & set(all_tables))}")


if __name__ == "__main__":
    main()
