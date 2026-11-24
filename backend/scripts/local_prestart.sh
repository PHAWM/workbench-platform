#! /usr/bin/env bash

set -e
set -x

export PYTHONPATH=$(pwd)

# Load local env
set -a
source deploy/.env.multi-tenant
set +a

# Wait for DB
python src/backend_prestart.py

# Run migrations
alembic upgrade head

# Seed initial data
python scripts/migrations/run_migration.py

# Provision PHAWM-SAM and PHAWM-ANNIF tenant schemas
python scripts/migrations/init_default_tenant.py
