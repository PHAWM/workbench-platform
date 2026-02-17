#!/usr/bin/env python3
"""
Run the v4 CSV-based migration.

Usage:
    python scripts/migrations/v4/run_migration.py

This will:
1. Create two test accounts:
   - test-audit-instigator@company.com (audit instigator)
   - test-auditor@company.com (auditor)
2. Load all other data from CSV files in storage/seed_data/
3. Set up complete audit structure with all necessary mappings
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import SQLModel, Session, create_engine, select
from src.database import create_db_and_tables, SQL_CONNECTION_STRING
from scripts.migrations.csv_loader import run_csv_migration


def main():
    """Run the migration."""
    print("Starting v4 migration...")

    engine = create_engine(SQL_CONNECTION_STRING)
        
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    session = Session(engine)
    
    with Session(engine) as session:
        result = run_csv_migration(session)

    print("\nMigration completed successfully!")
    return result


if __name__ == "__main__":
    main()
