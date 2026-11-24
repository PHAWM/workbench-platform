from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from src.api.deps import get_db, get_current_active_superuser
from src.database import provision_tenant_schema, get_tenant_engine
from src.models.tenant import Tenant, TenantCreate, TenantRead
from src.models.users import TenantAdminCreate, UserPublic
from src.services.user_service import create_tenant_admin

router = APIRouter(prefix="/tenants", tags=["Tenants"])


class TenantProvisionRequest(BaseModel):
    tenant: TenantCreate
    admin: TenantAdminCreate


class TenantProvisionResponse(BaseModel):
    tenant: TenantRead
    admin: UserPublic


@router.post("/", response_model=TenantProvisionResponse)
def create_tenant(
    body: TenantProvisionRequest,
    session: Session = Depends(get_db),
    _: None = Depends(get_current_active_superuser),
):
    """
    Register a new tenant, provision its Postgres schema, and create the
    first tenant admin user inside that schema. Superuser only.

    The admin user receives UserRoles.permissions = {"tenant_admin": True}
    and can subsequently invite and manage all users within the tenant.
    """
    tenant_in = body.tenant
    admin_in = body.admin

    existing = session.get(Tenant, tenant_in.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Tenant '{tenant_in.id}' already exists")

    schema = tenant_in.id.lower().replace("-", "_")

    tenant = Tenant(
        id=tenant_in.id,
        display_name=tenant_in.display_name,
        db_schema=schema,
        contact_email=tenant_in.contact_email,
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    try:
        provision_tenant_schema(schema)
    except Exception as e:
        session.delete(tenant)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to provision schema: {e}")

    try:
        tenant_engine = get_tenant_engine(schema)
        with Session(tenant_engine) as tenant_session:
            admin_user = create_tenant_admin(session=tenant_session, admin_in=admin_in)
    except Exception as e:
        # Schema exists but admin creation failed — tenant still usable, flag the error
        raise HTTPException(
            status_code=500,
            detail=f"Tenant schema created but admin user creation failed: {e}",
        )

    # Ensure the tenant's S3 bucket exists (no-op if STORAGE_BACKEND != s3)
    try:
        from src.services.utility_service.s3_storage_service import get_storage_manager
        get_storage_manager(schema)
    except Exception as e:
        # Non-fatal — bucket can be created later; don't block tenant provisioning
        print(f"Warning: could not ensure S3 bucket for tenant '{schema}': {e}")

    return TenantProvisionResponse(tenant=tenant, admin=admin_user)


@router.get("/", response_model=list[TenantRead])
def list_tenants(
    session: Session = Depends(get_db),
    _: None = Depends(get_current_active_superuser),
):
    """List all registered tenants. Superuser only."""
    return session.exec(select(Tenant)).all()


@router.delete("/{tenant_id}")
def deactivate_tenant(
    tenant_id: str,
    session: Session = Depends(get_db),
    _: None = Depends(get_current_active_superuser),
):
    """Deactivate a tenant (does not drop the schema). Superuser only."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.is_active = False
    session.add(tenant)
    session.commit()
    return {"detail": f"Tenant '{tenant_id}' deactivated"}
