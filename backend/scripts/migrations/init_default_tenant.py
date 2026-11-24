#!/usr/bin/env python3
"""
Provision the default PHAWM tenants at deployment time.

    phawm_sam   — PHAWM-SAM   (SAM model use-case)
    phawm_annif — PHAWM-ANNIF (ANNIF model use-case)
    demo        — PHAWM Demo  (combined SAM + Annif applications)

Creates the tenant registry entries, provisions their Postgres schemas with
all Alembic migrations, and seeds each schema with CSV data.

Safe to run multiple times (idempotent — already-existing records are skipped).

Usage:
    python scripts/migrations/init_default_tenant.py            # all tenants
    python scripts/migrations/init_default_tenant.py --only demo
    python scripts/migrations/init_default_tenant.py --only demo phawm_sam
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, create_engine
from src.database import engine, provision_tenant_schema, SQL_CONNECTION_STRING
from src.models.tenant import Tenant
from scripts.migrations.csv_loader import (
    run_csv_migration,
    add_audit_roles,
    load_categories_from_csv,
    load_taxonomy_groups_from_csv,
    load_taxonomy_mappings_from_csv,
)


def _ensure_tenant_s3_bucket(tenant_id: str) -> None:
    """Create the tenant's S3 bucket if STORAGE_BACKEND=s3. Idempotent."""
    from src.core.config import settings
    if settings.STORAGE_BACKEND != "s3":
        return
    from src.services.utility_service.s3_storage_service import get_storage_manager
    try:
        get_storage_manager(tenant_id)
        print(f"  [{tenant_id}] S3 bucket ensured.")
    except Exception as e:
        print(f"  [{tenant_id}] Warning: could not ensure S3 bucket: {e}")

TENANTS = [
    {"id": "phawm_sam",   "display_name": "PHAWM-SAM",   "allowed_apps": ["SAM"]},
    {"id": "phawm_annif", "display_name": "PHAWM-ANNIF", "allowed_apps": ["Annif"]},
    {"id": "demo",        "display_name": "PHAWM Demo",  "allowed_apps": ["SAM", "Annif"]},
]


def _register_tenant(session: Session, tenant_id: str, display_name: str) -> bool:
    """Register tenant in the public registry. Returns True if newly created."""
    existing = session.get(Tenant, tenant_id)
    if existing:
        print(f"  [{tenant_id}] Already registered — skipping registry entry.")
        return False
    session.add(Tenant(id=tenant_id, display_name=display_name, db_schema=tenant_id))
    session.commit()
    print(f"  [{tenant_id}] Registered in tenant registry.")
    return True


def _seed_tenant(schema: str, allowed_apps: list) -> None:
    """Run the CSV seed migration scoped to the tenant's schema."""
    tenant_engine = create_engine(
        SQL_CONNECTION_STRING,
        connect_args={"options": f"-csearch_path={schema},public"},
    )
    with Session(tenant_engine) as session:
        run_csv_migration(session, allowed_apps=allowed_apps)
    print(f"  [{schema}] Seed data loaded.")


def _ensure_baseline(schema: str) -> None:
    """Seed audit roles, event categories, taxonomy groups and their mappings.

    Idempotent — safe for existing tenants. Categories and taxonomies must
    be loaded before the mappings since taxonomy_mappings.csv references
    their auto-generated ids.
    """
    tenant_engine = create_engine(
        SQL_CONNECTION_STRING,
        connect_args={"options": f"-csearch_path={schema},public"},
    )
    with Session(tenant_engine) as session:
        add_audit_roles(session)
        load_categories_from_csv(session)
        load_taxonomy_groups_from_csv(session)
        load_taxonomy_mappings_from_csv(session)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="TENANT_ID",
        default=None,
        help="Limit provisioning to the given tenant ids. Default: all known tenants.",
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    known_ids = {t["id"] for t in TENANTS}
    if args.only:
        unknown = set(args.only) - known_ids
        if unknown:
            print(f"ERROR: unknown tenant id(s): {sorted(unknown)}. Known: {sorted(known_ids)}", file=sys.stderr)
            sys.exit(2)
        targets = [t for t in TENANTS if t["id"] in set(args.only)]
        print(f"Provisioning PHAWM tenants (filtered): {[t['id'] for t in targets]}")
    else:
        targets = TENANTS
        print("Provisioning default PHAWM tenants...")

    with Session(engine) as registry_session:
        for t in targets:
            tenant_id = t["id"]
            display_name = t["display_name"]
            print(f"\n→ {display_name} ({tenant_id})")

            is_new = _register_tenant(registry_session, tenant_id, display_name)

            # Always ensure schema + migrations are current
            provision_tenant_schema(tenant_id)
            print(f"  [{tenant_id}] Schema provisioned and migrations applied.")

            # Ensure the tenant's S3 bucket exists
            _ensure_tenant_s3_bucket(tenant_id)

            if is_new:
                _seed_tenant(tenant_id, t["allowed_apps"])
            else:
                # Tenant existed before this run, so we skip the full CSV seed
                # to avoid clobbering customer data — but audit roles and
                # event categories are baseline reference data and must always
                # be present, so make sure they exist regardless.
                _ensure_baseline(tenant_id)
                print(f"  [{tenant_id}] Audit roles + categories + taxonomies ensured (full seed skipped — tenant already existed).")

    print(f"\n{len(targets)} tenant(s) ready.")


if __name__ == "__main__":
    main()
