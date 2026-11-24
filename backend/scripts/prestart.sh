#! /usr/bin/env bash

set -e
set -x

# Set variables depending on which platform the script runs
if [ -n "$GITHUB_ACTIONS" ]; then
   export PYTHONPATH=$(pwd)
else
   export PYTHONPATH=/app
fi

# Let the DB start
python src/backend_prestart.py

# Run migrations on the public schema (creates Tenant table + all shared tables)
alembic upgrade head

# Create initial data in DB and seed the default tenant
python scripts/migrations/run_migration.py

# Ensure the default tenant schema exists and is up to date
python scripts/migrations/init_default_tenant.py
