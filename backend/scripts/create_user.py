#!/usr/bin/env python3
"""
Create a user inside an existing tenant schema.

Usage:
    python scripts/create_user.py \\
        --tenant   phawm_sam \\
        --email    user@example.com \\
        --name     "Jane Smith" \\
        --username jsmith

    # With an explicit env file (e.g. multi-tenant DB):
    ENV_FILE=../../deploy/.env.multi-tenant python scripts/create_user.py ...

Options:
    --tenant        Tenant schema name (e.g. phawm_sam)
    --email         User email address
    --name          Full name
    --username      Login username
    --password      Password (min 8 chars). Prompted securely if omitted.
    --organisation  Organisation name (optional)
    --admin         Grant tenant_admin permissions (flag, default: False)
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

from src.database import get_tenant_engine
from src.models.tenant import Tenant
from src.database import engine as public_engine
from src.models.users import UserCreate, TenantAdminCreate, UserRoles
from src.services.user_service import create_user, create_tenant_admin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a user inside an existing tenant schema.")
    parser.add_argument("--tenant",       required=True, help="Tenant schema name, e.g. phawm_sam")
    parser.add_argument("--email",        required=True, help="User email address")
    parser.add_argument("--name",         required=True, dest="full_name", help="Full name")
    parser.add_argument("--username",     required=True, help="Login username")
    parser.add_argument("--password",     default=None,  help="Password (min 8 chars). Prompted if omitted.")
    parser.add_argument("--organisation", default="Not Specified", help="Organisation name")
    parser.add_argument("--admin",        action="store_true", help="Grant tenant_admin permissions")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 1. Verify the tenant exists and resolve its db_schema
    with Session(public_engine) as session:
        tenant = session.get(Tenant, args.tenant)
        if not tenant:
            print(f"ERROR: Tenant '{args.tenant}' not found in the registry.", file=sys.stderr)
            print("       Run: python scripts/create_tenant.py to create it first.", file=sys.stderr)
            sys.exit(1)
        if not tenant.is_active:
            print(f"ERROR: Tenant '{args.tenant}' exists but is inactive.", file=sys.stderr)
            sys.exit(1)
        schema = tenant.db_schema  # use db_schema, not id — may differ in case

    # 2. Prompt for password if not supplied
    password = args.password
    if not password:
        password = getpass.getpass(f"Password for {args.email}: ")
        confirm  = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("ERROR: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    # 3. Check for duplicate email in the tenant schema
    tenant_engine = get_tenant_engine(schema)
    with Session(tenant_engine) as session:
        from src.models.users import User
        existing = session.exec(select(User).where(User.email == args.email.lower())).first()
        if existing:
            print(f"ERROR: A user with email '{args.email}' already exists in tenant '{args.tenant}'.", file=sys.stderr)
            sys.exit(1)

    # 4. Create the user
    try:
        tenant_engine = get_tenant_engine(schema)
        with Session(tenant_engine) as session:
            if args.admin:
                admin_in = TenantAdminCreate(
                    email=args.email,
                    full_name=args.full_name,
                    username=args.username,
                    password=password,
                    organisation=args.organisation,
                )
                user = create_tenant_admin(session=session, admin_in=admin_in)
            else:
                user_in = UserCreate(
                    email=args.email,
                    full_name=args.full_name,
                    username=args.username,
                    password=password,
                    organisation=args.organisation,
                    is_active=True,
                    is_verified=True,
                    is_superuser=False,
                )
                user = create_user(session=session, user_create=user_in)
            user_email = user.email

    except Exception as e:
        print(f"ERROR: Failed to create user.\n{e}", file=sys.stderr)
        sys.exit(1)

    role_label = "tenant_admin" if args.admin else "user"
    print(f"\nUser created successfully in tenant '{args.tenant}'.")
    print(f"  Email  : {user_email}")
    print(f"  Name   : {args.full_name}")
    print(f"  Role   : {role_label}")


if __name__ == "__main__":
    main()
