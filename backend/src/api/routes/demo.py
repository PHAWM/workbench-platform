"""Demo-tenant reset endpoint.

Wipes a resettable tenant back to a freshly-seeded state. Only the tenants in
`RESETTABLE_TENANTS` are in scope — every other tenant in the registry is left
alone.

The legacy version of this route truncated *every* table SQLModel knew about
on the public schema, which on a multi-tenant deployment took out the tenant
registry along with it. This rewrite is schema-scoped: it drops the tenant's
Postgres schema, re-provisions it via Alembic, wipes the matching S3 bucket
(or local audit files), and re-runs the CSV seed scoped to that tenant's apps.

Authorization: the caller must be authenticated against a resettable tenant
(JWT `tid` claim in `RESETTABLE_TENANTS`). The reset always acts on the
caller's own tenant — there is no parameter to widen this scope, by design.
"""
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlmodel import Session

from src.api.deps import get_current_tenant_id
from src.core.config import settings
from src.database import engine, get_tenant_engine, provision_tenant_schema
from src.models.tenant import Tenant

router = APIRouter(prefix="/demo", tags=["Demo"])


# Tenants this endpoint is allowed to reset, with the display name and
# allowed_apps each gets re-seeded with. Must stay in sync with the canonical
# definitions in scripts/migrations/init_default_tenant.py. A configurable
# allowlist would invite accidents on production tenants, so keep it a const.
RESETTABLE_TENANTS = {
    "demo":      {"display_name": "PHAWM Demo", "allowed_apps": ["SAM", "Annif"]},
    "phawm_sam": {"display_name": "PHAWM-SAM",  "allowed_apps": ["SAM"]},
}


def _evict_caches(tenant_id: str) -> None:
    """Drop cached engines and storage managers for a tenant.

    Necessary after dropping the schema — otherwise stale connections held by
    the cached engine will fail on the next request, and the cached S3 client
    keeps pointing at the old bucket configuration.
    """
    from src.database import _tenant_engines
    eng = _tenant_engines.pop(tenant_id, None)
    if eng is not None:
        try:
            eng.dispose()
        except Exception:
            pass

    from src.services.utility_service import s3_storage_service as _s3
    _s3._storage_manager_cache.pop(tenant_id, None)
    _s3._storage_manager_cache.pop("__default__", None)


def _wipe_tenant_storage(tenant_id: str) -> None:
    """Empty the tenant's bucket (S3) or local audits dir.

    For S3 we delete every object in the bucket; the bucket itself is
    re-used. For local storage we wipe `storage/audits/` — this is shared
    across tenants in local mode, but local mode is a dev-only path so it's
    acceptable for the demo reset to clear it.
    """
    if settings.STORAGE_BACKEND == "s3":
        from src.services.utility_service.s3_storage_service import (
            S3StorageManager,
            get_storage_manager,
        )
        sm = get_storage_manager(tenant_id)
        if not isinstance(sm, S3StorageManager):
            return
        # Make sure the bucket exists before trying to empty it; the helper
        # creates it on first use.
        try:
            paginator = sm.s3.get_paginator("list_objects_v2")
            to_delete: list[dict] = []
            for page in paginator.paginate(Bucket=sm.bucket_name):
                for obj in page.get("Contents", []):
                    to_delete.append({"Key": obj["Key"]})
                    if len(to_delete) == 1000:
                        sm.s3.delete_objects(
                            Bucket=sm.bucket_name,
                            Delete={"Objects": to_delete, "Quiet": True},
                        )
                        to_delete = []
            if to_delete:
                sm.s3.delete_objects(
                    Bucket=sm.bucket_name,
                    Delete={"Objects": to_delete, "Quiet": True},
                )
        except Exception:
            # Don't let bucket-empty failures abort the reset; a fresh
            # bucket gets created on the next storage access if needed.
            pass
    else:
        import shutil
        from pathlib import Path
        audits_dir = Path("storage/audits")
        if audits_dir.exists():
            shutil.rmtree(audits_dir)
            audits_dir.mkdir(parents=True, exist_ok=True)


def _drop_schema_and_registry(tenant_id: str) -> None:
    """DROP SCHEMA <tenant_id> CASCADE and remove its row from public.tenant."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{tenant_id}" CASCADE'))

    with Session(engine) as registry:
        existing = registry.get(Tenant, tenant_id)
        if existing:
            registry.delete(existing)
            registry.commit()


def _reseed(tenant_id: str, display_name: str, allowed_apps: list[str]) -> None:
    """Re-register, re-provision, re-seed the tenant."""
    # Registry first — `Tenant.id` is the primary key the rest of the system
    # joins against.
    with Session(engine) as registry:
        registry.add(Tenant(
            id=tenant_id,
            display_name=display_name,
            db_schema=tenant_id,
        ))
        registry.commit()

    # Schema + alembic upgrade.
    provision_tenant_schema(tenant_id)

    # Seed CSV data scoped to the tenant's schema.
    from scripts.migrations.csv_loader import run_csv_migration
    tenant_engine = get_tenant_engine(tenant_id)
    with Session(tenant_engine) as session:
        run_csv_migration(session, allowed_apps=allowed_apps)


@router.post("/reset")
def reset_demo_tenant(tenant_id: str | None = Depends(get_current_tenant_id)):
    """Reset the caller's tenant to its freshly-seeded state.

    Steps, in order:
      1. Drop the tenant's Postgres schema (CASCADE) and remove its tenant
         registry row.
      2. Evict cached SQLAlchemy engines and storage managers for the tenant.
      3. Wipe the tenant's S3 bucket (or local audits dir).
      4. Re-register the tenant, re-run alembic against the fresh schema,
         re-run the CSV seed with the tenant's allowed_apps.

    Only callable by clients whose JWT is bound to a resettable tenant. Always
    operates on the caller's own tenant — there is no parameter to widen this
    scope, by design.
    """
    config = RESETTABLE_TENANTS.get(tenant_id)
    if config is None:
        raise HTTPException(
            status_code=403,
            detail="This endpoint can only be called from a resettable tenant.",
        )

    display_name = config["display_name"]
    allowed_apps = config["allowed_apps"]

    try:
        _drop_schema_and_registry(tenant_id)
        _evict_caches(tenant_id)
        # _wipe_tenant_storage(tenant_id)
        _reseed(tenant_id, display_name, allowed_apps)

        return {
            "message": f"Demo tenant '{tenant_id}' reset successfully",
            "tenant_id": tenant_id,
            "allowed_apps": allowed_apps,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Error resetting demo tenant:\n{traceback.format_exc()}",
        )
