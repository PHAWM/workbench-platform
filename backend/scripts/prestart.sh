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

# Run migrations
alembic upgrade head

# Create initial data in DB
python scripts/migrations/run_migration.py
