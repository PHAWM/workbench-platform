#!/usr/bin/env python3
"""
Create a new tenant and its first admin user.

Usage:
    python scripts/create_tenant.py \\
        --id uni_glasgow \\
        --name "University of Glasgow" \\
        --email admin@uni-glasgow.ac.uk \\
        --admin-email jane.smith@uni-glasgow.ac.uk \\
        --admin-name "Jane Smith" \\
        --admin-username jsmith \\
        --admin-password "SecurePassword1!"

Options:
    --id              Tenant slug (lowercase, underscores only). Used as the Postgres schema name.
    --name            Human-readable display name.
    --email           Contact email for the tenant (optional).
    --admin-email     Email address of the first tenant admin user.
    --admin-name      Full name of the first tenant admin user.
    --admin-username  Username of the first tenant admin user.
    --admin-password  Password for the first tenant admin user (min 8 chars).
                      Omit to be prompted securely.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load env before src.database is imported so the engine uses the right credentials.
from dotenv import load_dotenv
_env_file = os.environ.get("ENV_FILE", "deploy/.env")
load_dotenv(dotenv_path=_env_file, override=True)

from sqlmodel import Session, select

from src.database import engine, provision_tenant_schema, get_tenant_engine
from src.models.tenant import Tenant
from src.models.users import TenantAdminCreate
from src.services.user_service import create_tenant_admin
from scripts.migrations.csv_loader import (
    add_audit_roles,
    load_categories_from_csv,
    load_taxonomy_groups_from_csv,
    load_taxonomy_mappings_from_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a new tenant and its first admin user.")
    parser.add_argument("--id", required=True, dest="tenant_id", help="Tenant slug, e.g. uni_glasgow")
    parser.add_argument("--name", required=True, dest="display_name", help="Display name, e.g. 'University of Glasgow'")
    parser.add_argument("--email", default=None, dest="contact_email", help="Contact email for the tenant (optional)")
    parser.add_argument("--admin-email", required=True, help="Admin user email")
    parser.add_argument("--admin-name", required=True, help="Admin user full name")
    parser.add_argument("--admin-username", required=True, help="Admin user username")
    parser.add_argument("--admin-password", default=None, help="Admin user password (prompted if omitted)")
    parser.add_argument("--organisation", default=None, help="Organisation name stored on the admin user (defaults to tenant display name)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Derive schema name — same logic as the API route
    schema = args.tenant_id.lower().replace("-", "_")

    # Prompt for password if not supplied
    password = args.admin_password
    if not password:
        password = getpass.getpass(f"Password for {args.admin_email}: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("ERROR: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 1. Register tenant in the public schema
    # -------------------------------------------------------------------------
    with Session(engine) as session:
        existing = session.get(Tenant, args.tenant_id)
        if existing:
            print(f"ERROR: Tenant '{args.tenant_id}' already exists.", file=sys.stderr)
            sys.exit(1)

        tenant = Tenant(
            id=args.tenant_id,
            display_name=args.display_name,
            db_schema=schema,
            contact_email=args.contact_email,
        )
        session.add(tenant)
        session.commit()
        print(f"[1/3] Tenant '{args.tenant_id}' registered in public.tenant.")

    # -------------------------------------------------------------------------
    # 2. Provision the Postgres schema and run Alembic migrations
    # -------------------------------------------------------------------------
    try:
        provision_tenant_schema(schema)
        print(f"[2/4] Schema '{schema}' provisioned and migrations applied.")
    except Exception as e:
        # Roll back the registry entry so the tenant can be re-created cleanly
        with Session(engine) as session:
            tenant = session.get(Tenant, args.tenant_id)
            if tenant:
                session.delete(tenant)
                session.commit()
        print(f"ERROR: Schema provisioning failed — registry entry rolled back.\n{e}", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 3. Seed baseline reference data into the new schema.
    # Audit creation hardcodes AuditRoles.id == 1 == audit_instigator, so
    # roles must exist before the schema sees any traffic. Event categories,
    # taxonomy groups, and the mappings between them are loaded from
    # storage/seed_data/*.csv (with built-in defaults if a CSV is absent).
    # Order matters: categories + taxonomies must exist before the mapping
    # rows reference their ids.
    # -------------------------------------------------------------------------
    try:
        tenant_engine = get_tenant_engine(schema)
        with Session(tenant_engine) as session:
            add_audit_roles(session)
            load_categories_from_csv(session)
            load_taxonomy_groups_from_csv(session)
            load_taxonomy_mappings_from_csv(session)
        print(f"[3/4] Audit roles, categories, taxonomies and mappings seeded in '{schema}'.")
    except Exception as e:
        print(f"ERROR: Baseline seed failed — schema exists but reference data is incomplete.\n{e}", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 4. Create the first tenant admin user inside the new schema
    # -------------------------------------------------------------------------
    try:
        admin_in = TenantAdminCreate(
            email=args.admin_email,
            full_name=args.admin_name,
            username=args.admin_username,
            password=password,
            organisation=args.organisation or args.display_name,
        )
        tenant_engine = get_tenant_engine(schema)
        with Session(tenant_engine) as session:
            admin = create_tenant_admin(session=session, admin_in=admin_in)
            admin_email = admin.email  # read while session is still open
        print(f"[4/4] Admin user '{admin_email}' created with tenant_admin permissions.")
    except Exception as e:
        print(f"ERROR: Admin user creation failed — schema exists but has no admin.\n{e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nTenant '{args.display_name}' ({args.tenant_id}) is ready.")
    print(f"  Schema : {schema}")
    print(f"  Admin  : {admin_email}")


if __name__ == "__main__":
    main()
