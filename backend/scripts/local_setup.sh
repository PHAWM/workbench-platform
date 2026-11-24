#! /usr/bin/env bash
# ---------------------------------------------------------------------------
# local_setup.sh — run this once to set up PHAWM locally without Docker
#
# Prerequisites:
#   - Python 3.11+ virtual environment activated  (source .venv/bin/activate)
#   - PostgreSQL running locally on port 5432
#   - deploy/.env file configured
#
# Usage:
#   bash scripts/local_setup.sh
#   bash scripts/local_setup.sh --reset   # drop & recreate everything
# ---------------------------------------------------------------------------

set -e

RESET=false
if [[ "$1" == "--reset" ]]; then
    RESET=true
fi

# --- Load env ---------------------------------------------------------------
ENV_FILE="deploy/.env.multi-tenant"
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Copy deploy/.env.example and fill it in."
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

export PYTHONPATH=$(pwd)
export ENV_FILE   # tells database.py and alembic/env.py which file to load

echo "======================================================================"
echo " PHAWM Local Setup"
echo " DB: ${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "======================================================================"

# --- Wait for Postgres ------------------------------------------------------
echo ""
echo "[1/5] Checking PostgreSQL connection..."
# Connect to the default 'postgres' database just to confirm the server is up
PGPASSWORD="${POSTGRES_PASSWORD}" psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d postgres \
    -c "SELECT 1" > /dev/null

# --- Optionally reset -------------------------------------------------------
if [ "$RESET" = true ]; then
    echo ""
    echo "[!] --reset: dropping and recreating database '${POSTGRES_DB}'..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS \"${POSTGRES_DB}\";"
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d postgres \
        -c "CREATE DATABASE \"${POSTGRES_DB}\";"
    echo "    Database '${POSTGRES_DB}' recreated."
else
    # Create database if it doesn't already exist
    DB_EXISTS=$(PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d postgres \
        -tAc "SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB}'")
    if [ "$DB_EXISTS" != "1" ]; then
        PGPASSWORD="${POSTGRES_PASSWORD}" psql \
            -h "${POSTGRES_HOST}" \
            -p "${POSTGRES_PORT}" \
            -U "${POSTGRES_USER}" \
            -d postgres \
            -c "CREATE DATABASE \"${POSTGRES_DB}\";"
        echo "    Database '${POSTGRES_DB}' created."
    else
        echo "    Database '${POSTGRES_DB}' already exists."
    fi
fi

# --- Alembic migrations (public schema) -------------------------------------
echo ""
echo "[2/5] Running Alembic migrations on public schema..."
alembic upgrade head

# --- Seed data --------------------------------------------------------------
echo ""
echo "[3/5] Seeding initial data (roles, users, audits)..."
python scripts/migrations/run_migration.py

# --- Provision PHAWM tenants ------------------------------------------------
echo ""
echo "[4/5] Provisioning PHAWM-SAM and PHAWM-ANNIF tenant schemas..."
python scripts/migrations/init_default_tenant.py

# --- Done -------------------------------------------------------------------
echo ""
echo "[5/5] Setup complete."
echo ""
echo "  Tenants provisioned:"
echo "    phawm_sam   → use header  X-Tenant-ID: phawm_sam"
echo "    phawm_annif → use header  X-Tenant-ID: phawm_annif"
echo ""
echo "  Start the API:"
echo "    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
